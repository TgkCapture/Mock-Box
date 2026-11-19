"""In-memory payment simulator behind /api/payments.

Two flows, both driven by test inputs so every outcome can be reproduced on demand:

* **Mobile money** (Airtel Money, TNM Mpamba, M-Pesa, MTN MoMo style). Initiating returns
  ``pending`` (the customer is "entering their PIN"), then the payment settles after
  ``settle_after_ms`` and a webhook is POSTed to ``callback_url``. The phone number's last
  three digits pick the outcome (see ``MOBILE_TEST_SUFFIXES``).
* **Cards.** Settle immediately, except the 3-D Secure test card which returns
  ``requires_action`` until ``/authorize`` is called. The card number picks the outcome
  (see ``TEST_CARDS``); any other Luhn-valid number succeeds.

Any outcome can also be forced with ``"simulate": "<outcome>"`` in the request body.
Webhooks are signed (``X-Mockbox-Signature: sha256=<hmac>``) when ``callback_secret`` is set.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import __version__, generators

log = logging.getLogger(__name__)

EXTENSION_KEY = "mockbox.payments"
DEFAULT_SETTLE_MS = 3000
MAX_SETTLE_MS = 600_000
MAX_PAYMENTS = 10_000
MAX_AMOUNT = 1_000_000_000
WEBHOOK_TIMEOUT = 5

PROVIDERS = {
    "airtel": "Airtel Money",
    "mpamba": "TNM Mpamba",
    "mpesa": "M-Pesa",
    "mtn": "MTN MoMo",
}

# outcome -> (final status, failure message). "success" has no failure.
OUTCOMES: Dict[str, Tuple[str, Optional[str]]] = {
    "success": ("succeeded", None),
    "insufficient_funds": ("failed", "The account has insufficient funds"),
    "cancelled": ("failed", "The customer declined the payment prompt"),
    "timeout": ("expired", "The customer did not respond to the payment prompt in time"),
    "account_not_found": ("failed", "No mobile money account is registered to this number"),
    "card_declined": ("failed", "The card was declined"),
    "expired_card": ("failed", "The card has expired"),
    "incorrect_cvc": ("failed", "The card's security code is incorrect"),
    "processing_error": ("failed", "An error occurred while processing the card"),
    "requires_action": ("requires_action", None),
}
MOBILE_OUTCOMES = ("success", "insufficient_funds", "cancelled", "timeout", "account_not_found")
CARD_OUTCOMES = (
    "success", "insufficient_funds", "card_declined", "expired_card", "incorrect_cvc",
    "processing_error", "requires_action",
)

MOBILE_TEST_SUFFIXES = {
    "001": "insufficient_funds",
    "002": "cancelled",
    "003": "timeout",
    "004": "account_not_found",
}
TEST_CARDS = {
    "4111111111111111": "success",
    "5555555555554444": "success",
    "4000000000001000": "card_declined",
    "4000000000002008": "insufficient_funds",
    "4000000000003006": "expired_card",
    "4000000000004004": "incorrect_cvc",
    "4000000000005001": "requires_action",
    "4000000000006009": "processing_error",
}

_PHONE_RE = re.compile(r"^\+?\d{9,15}$")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")

Payment = Dict[str, Any]


class PaymentError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------- plumbing
# Module-level so tests can replace them.
def schedule(delay_seconds: float, fn: Callable[[], None]) -> None:
    timer = threading.Timer(delay_seconds, fn)
    timer.daemon = True
    timer.start()


def run_async(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


def post_json(url: str, body: bytes, headers: Dict[str, str]) -> int:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT) as resp:  # noqa: S310 (scheme checked)
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return generators.iso(value.replace(microsecond=0))


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


# --------------------------------------------------------------------------- validation
def _amount(data: Dict[str, Any]) -> float:
    amount = data.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise PaymentError(400, "amount is required and must be a number")
    if not 0 < amount <= MAX_AMOUNT:
        raise PaymentError(400, f"amount must be greater than 0 and at most {MAX_AMOUNT}")
    return amount


def _currency(data: Dict[str, Any], default: str) -> str:
    currency = data.get("currency", default)
    if not isinstance(currency, str) or not _CURRENCY_RE.match(currency):
        raise PaymentError(400, "currency must be a 3-letter code such as MWK or USD")
    return currency.upper()


def _optional_str(data: Dict[str, Any], key: str, max_length: int = 200) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > max_length:
        raise PaymentError(400, f"{key} must be a string of at most {max_length} characters")
    return value


def _callback_url(data: Dict[str, Any]) -> Optional[str]:
    url = _optional_str(data, "callback_url", 2000)
    if url is not None and not url.startswith(("http://", "https://")):
        raise PaymentError(400, "callback_url must be an http:// or https:// URL")
    return url


def _metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise PaymentError(400, "metadata must be a JSON object")
    return metadata


def _simulate(data: Dict[str, Any], allowed: Tuple[str, ...]) -> Optional[str]:
    outcome = data.get("simulate")
    if outcome is not None and outcome not in allowed:
        raise PaymentError(400, f"simulate must be one of {list(allowed)}")
    return outcome


def _settle_ms(data: Dict[str, Any]) -> int:
    value = data.get("settle_after_ms", DEFAULT_SETTLE_MS)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_SETTLE_MS:
        raise PaymentError(400, f"settle_after_ms must be an integer between 0 and {MAX_SETTLE_MS}")
    return value


def normalize_phone(raw: Any) -> str:
    if not isinstance(raw, str):
        raise PaymentError(400, "phone is required")
    phone = re.sub(r"[\s\-()]", "", raw)
    if not _PHONE_RE.match(phone):
        raise PaymentError(400, "phone must contain 9 to 15 digits, optionally starting with +")
    return phone


def luhn_valid(number: str) -> bool:
    total = 0
    for i, char in enumerate(reversed(number)):
        digit = int(char)
        if i % 2:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def card_brand(number: str) -> str:
    if number.startswith("4"):
        return "visa"
    if number[:2] in {"51", "52", "53", "54", "55"} or 2221 <= int(number[:4]) <= 2720:
        return "mastercard"
    if number[:2] in {"34", "37"}:
        return "amex"
    return "unknown"


def _card(data: Dict[str, Any]) -> Tuple[str, int, int]:
    raw = data.get("card_number")
    if not isinstance(raw, str):
        raise PaymentError(400, "card_number is required")
    number = re.sub(r"[\s\-]", "", raw)
    if not number.isdigit() or not 12 <= len(number) <= 19 or not luhn_valid(number):
        raise PaymentError(400, "card_number is not a valid card number")
    month, year = data.get("exp_month"), data.get("exp_year")
    if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12:
        raise PaymentError(400, "exp_month must be an integer between 1 and 12")
    if not isinstance(year, int) or isinstance(year, bool) or not (0 <= year <= 99 or 2000 <= year <= 2100):
        raise PaymentError(400, "exp_year must be a 2- or 4-digit year")
    cvc = data.get("cvc")
    if not isinstance(cvc, str) or not re.fullmatch(r"\d{3,4}", cvc):
        raise PaymentError(400, "cvc must be a string of 3 or 4 digits")
    return number, month, year + 2000 if year < 100 else year


# --------------------------------------------------------------------------- engine
class Payments:
    def __init__(self):
        self._lock = threading.RLock()
        self._payments: Dict[str, Payment] = {}
        self._idempotency: Dict[str, str] = {}
        # Internal per-payment state that is never shown to clients.
        self._outcome: Dict[str, str] = {}
        self._settle_at: Dict[str, datetime] = {}
        self._secret: Dict[str, str] = {}

    # ------------------------------------------------------------------ public
    def reset(self) -> int:
        with self._lock:
            count = len(self._payments)
            for state in (self._payments, self._idempotency, self._outcome, self._settle_at, self._secret):
                state.clear()
            return count

    def list(self) -> List[Payment]:
        with self._lock:
            for payment_id in list(self._settle_at):
                self._settle_if_due(payment_id)
            return [self._public(p) for p in self._payments.values()]

    def get(self, payment_id: str) -> Payment:
        with self._lock:
            self._require(payment_id)
            self._settle_if_due(payment_id)
            return self._public(self._payments[payment_id])

    def create_mobile_money(self, data: Dict[str, Any], idempotency_key: Optional[str] = None) -> Tuple[Payment, bool]:
        provider = data.get("provider")
        if provider not in PROVIDERS:
            raise PaymentError(400, f"provider must be one of {list(PROVIDERS)}")
        phone = normalize_phone(data.get("phone"))
        amount, currency = _amount(data), _currency(data, "MWK")
        settle_ms = _settle_ms(data)
        outcome = _simulate(data, MOBILE_OUTCOMES) or MOBILE_TEST_SUFFIXES.get(phone[-3:], "success")

        def build(now: datetime) -> Payment:
            return {
                "method": "mobile_money",
                "provider": provider,
                "provider_name": PROVIDERS[provider],
                "phone": phone,
                "status": "pending",
                "amount": amount,
                "currency": currency,
                "settles_at": _iso(now + timedelta(milliseconds=settle_ms)),
            }

        return self._create(data, idempotency_key, build, outcome, settle_ms)

    def create_card(self, data: Dict[str, Any], idempotency_key: Optional[str] = None) -> Tuple[Payment, bool]:
        number, month, year = _card(data)
        amount, currency = _amount(data), _currency(data, "USD")
        outcome = _simulate(data, CARD_OUTCOMES) or TEST_CARDS.get(number, "success")
        if outcome == "success" and (year, month) < (_now().year, _now().month):
            outcome = "expired_card"

        def build(now: datetime) -> Payment:
            return {
                "method": "card",
                "card": {"brand": card_brand(number), "last4": number[-4:], "exp_month": month, "exp_year": year},
                "status": "pending",
                "amount": amount,
                "currency": currency,
            }

        return self._create(data, idempotency_key, build, outcome, 0)

    def complete(self, payment_id: str, outcome: Optional[str]) -> Payment:
        """Settle a pending mobile money payment now, optionally overriding its outcome."""
        with self._lock:
            payment = self._require(payment_id)
            self._settle_if_due(payment_id)
            if payment["status"] != "pending":
                raise PaymentError(409, f"Payment is already {payment['status']}")
            if outcome is not None:
                if outcome not in MOBILE_OUTCOMES:
                    raise PaymentError(400, f"outcome must be one of {list(MOBILE_OUTCOMES)}")
                self._outcome[payment_id] = outcome
            self._settle(payment_id)
            return self._public(payment)

    def authorize(self, payment_id: str, approve: bool) -> Payment:
        """Finish the 3-D Secure step of a card payment."""
        with self._lock:
            payment = self._require(payment_id)
            if payment["status"] != "requires_action":
                raise PaymentError(409, f"Payment is {payment['status']}, not requires_action")
            payment.pop("next_action", None)
            self._finish(payment, "success" if approve else "card_declined")
            return self._public(payment)

    def refund(self, payment_id: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Payment]:
        with self._lock:
            payment = self._require(payment_id)
            self._settle_if_due(payment_id)
            if payment["status"] not in ("succeeded", "partially_refunded"):
                raise PaymentError(409, f"Only succeeded payments can be refunded; this one is {payment['status']}")
            remaining = round(payment["amount"] - payment["amount_refunded"], 2)
            amount = _amount(data) if "amount" in data else remaining
            if amount > remaining:
                raise PaymentError(400, f"amount exceeds the refundable balance of {remaining}")
            refund = {
                "id": _new_id("re"),
                "amount": amount,
                "reason": _optional_str(data, "reason"),
                "created_at": _iso(_now()),
            }
            payment["refunds"].append(refund)
            payment["amount_refunded"] = round(payment["amount_refunded"] + amount, 2)
            payment["status"] = "refunded" if payment["amount_refunded"] >= payment["amount"] else "partially_refunded"
            payment["updated_at"] = refund["created_at"]
            self._notify(payment_id, "payment.refunded")
            return refund, self._public(payment)

    # ------------------------------------------------------------------ internals
    def _require(self, payment_id: str) -> Payment:
        if payment_id not in self._payments:
            raise PaymentError(404, f"Payment {payment_id!r} not found")
        return self._payments[payment_id]

    @staticmethod
    def _public(payment: Payment) -> Payment:
        return copy.deepcopy(payment)

    def _create(self, data, idempotency_key, build, outcome: str, settle_ms: int) -> Tuple[Payment, bool]:
        reference = _optional_str(data, "reference")
        description = _optional_str(data, "description")
        callback_url = _callback_url(data)
        secret = _optional_str(data, "callback_secret")
        metadata = _metadata(data)
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                return self.get(self._idempotency[idempotency_key]), True
            if len(self._payments) >= MAX_PAYMENTS:
                raise PaymentError(507, f"Payment limit of {MAX_PAYMENTS} reached; DELETE /api/payments to reset")
            now = _now()
            payment_id = _new_id("pay")
            payment: Payment = {"id": payment_id, "object": "payment", **build(now)}
            payment.update({
                "reference": reference,
                "description": description,
                "provider_reference": None,
                "failure": None,
                "amount_refunded": 0,
                "refunds": [],
                "metadata": metadata,
                "callback_url": callback_url,
                "webhooks": [],
                "created_at": _iso(now),
                "updated_at": _iso(now),
            })
            self._payments[payment_id] = payment
            self._outcome[payment_id] = outcome
            if secret:
                self._secret[payment_id] = secret
            if idempotency_key:
                self._idempotency[idempotency_key] = payment_id

            if payment["method"] == "mobile_money" and settle_ms > 0:
                self._settle_at[payment_id] = now + timedelta(milliseconds=settle_ms)
                schedule(settle_ms / 1000, lambda: self._settle_from_timer(payment_id))
            else:
                self._settle(payment_id)
            return self._public(payment), False

    def _settle_if_due(self, payment_id: str) -> None:
        with self._lock:
            due = self._settle_at.get(payment_id)
            if due is not None and _now() >= due:
                self._settle(payment_id)

    def _settle_from_timer(self, payment_id: str) -> None:
        # Timers and the wall clock can disagree by a few ms, so don't re-check the deadline.
        with self._lock:
            if payment_id in self._settle_at:
                self._settle(payment_id)

    def _settle(self, payment_id: str) -> None:
        self._settle_at.pop(payment_id, None)
        payment = self._payments.get(payment_id)
        if payment is None or payment["status"] != "pending":
            return
        payment.pop("settles_at", None)
        outcome = self._outcome.pop(payment_id, "success")
        if outcome == "requires_action":
            payment["status"] = "requires_action"
            payment["next_action"] = {
                "type": "3ds_authentication",
                "authorize_url": f"/api/payments/{payment_id}/authorize",
                "message": "POST {\"result\": \"approve\"} or {\"result\": \"deny\"} to the authorize_url",
            }
            payment["updated_at"] = _iso(_now())
            return
        self._finish(payment, outcome)

    def _finish(self, payment: Payment, outcome: str) -> None:
        status, message = OUTCOMES[outcome]
        payment["status"] = status
        payment["updated_at"] = _iso(_now())
        if status == "succeeded":
            payment["provider_reference"] = secrets.token_hex(5).upper()
        else:
            payment["failure"] = {"code": outcome, "message": message}
        self._notify(payment["id"], f"payment.{status}")

    def _notify(self, payment_id: str, event: str) -> None:
        payment = self._payments[payment_id]
        url = payment.get("callback_url")
        if not url:
            return
        delivery = {"event": event, "url": url, "status_code": None, "error": None, "sent_at": None}
        payment["webhooks"].append(delivery)
        body = json.dumps({"event": event, "data": self._public(payment)}).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"mock-box/{__version__}",
            "X-Mockbox-Event": event,
        }
        secret = self._secret.get(payment_id)
        if secret:
            headers["X-Mockbox-Signature"] = sign(secret, body)

        def deliver() -> None:
            sent_at = _iso(_now())
            try:
                status_code, error = post_json(url, body, headers), None
            except Exception as exc:  # network errors are reported on the payment, never raised
                status_code, error = None, str(exc) or exc.__class__.__name__
                log.warning("Webhook %s to %s failed: %s", event, url, error)
            with self._lock:
                delivery.update(status_code=status_code, error=error, sent_at=sent_at)

        run_async(deliver)


def get_payments() -> Payments:
    from flask import current_app

    return current_app.extensions[EXTENSION_KEY]
