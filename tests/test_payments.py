import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mockbox import payments as engine

MOBILE = {"provider": "airtel", "phone": "+265991234567", "amount": 5000}
CARD = {"card_number": "4111 1111 1111 1111", "exp_month": 12, "exp_year": 2099, "cvc": "123", "amount": 25}


@pytest.fixture
def webhooks(monkeypatch):
    """Run webhooks synchronously and capture them instead of sending HTTP requests."""
    sent = []
    monkeypatch.setattr(engine, "schedule", lambda delay, fn: None)
    monkeypatch.setattr(engine, "run_async", lambda fn: fn())

    def fake_post(url, body, headers):
        sent.append({"url": url, "body": json.loads(body), "raw": body, "headers": headers})
        return 200

    monkeypatch.setattr(engine, "post_json", fake_post)
    return sent


def mobile(client, **overrides):
    return client.post("/api/payments/mobile-money", json={**MOBILE, **overrides})


def card(client, **overrides):
    return client.post("/api/payments/cards", json={**CARD, **overrides})


# --------------------------------------------------------------------------- mobile money
def test_mobile_money_starts_pending(client, webhooks):
    resp = mobile(client, reference="INV-1")
    assert resp.status_code == 202
    body = resp.get_json()
    assert body["status"] == "pending" and body["provider_name"] == "Airtel Money"
    assert body["currency"] == "MWK" and body["reference"] == "INV-1" and "settles_at" in body
    assert resp.headers["Location"] == f"/api/payments/{body['id']}"
    assert client.get(resp.headers["Location"]).get_json()["status"] == "pending"


def test_mobile_money_settles_after_delay_on_poll(client, webhooks):
    payment = mobile(client, settle_after_ms=50).get_json()
    time.sleep(0.08)
    settled = client.get(f"/api/payments/{payment['id']}").get_json()
    assert settled["status"] == "succeeded" and settled["provider_reference"]
    assert "settles_at" not in settled


def test_mobile_money_settles_via_real_timer(client, monkeypatch):
    monkeypatch.setattr(engine, "run_async", lambda fn: fn())
    monkeypatch.setattr(engine, "post_json", lambda *a: 200)
    payment = mobile(client, settle_after_ms=20, callback_url="http://hook.test/x").get_json()
    payments = client.application.extensions[engine.EXTENSION_KEY]
    deadline = time.time() + 2
    while time.time() < deadline and payments._payments[payment["id"]]["status"] == "pending":
        time.sleep(0.01)
    assert payments._payments[payment["id"]]["webhooks"][0]["status_code"] == 200


@pytest.mark.parametrize(
    "suffix,status,code",
    [("001", "failed", "insufficient_funds"), ("002", "failed", "cancelled"),
     ("003", "expired", "timeout"), ("004", "failed", "account_not_found")],
)
def test_mobile_money_test_numbers(client, webhooks, suffix, status, code):
    payment = mobile(client, phone="0991234" + suffix, settle_after_ms=0).get_json()
    assert payment["status"] == status and payment["failure"]["code"] == code


def test_simulate_overrides_test_number(client, webhooks):
    payment = mobile(client, phone="0991234001", simulate="success", settle_after_ms=0).get_json()
    assert payment["status"] == "succeeded"


def test_complete_settles_now_and_can_override(client, webhooks):
    first = mobile(client, settle_after_ms=600000).get_json()
    done = client.post(f"/api/payments/{first['id']}/complete").get_json()
    assert done["status"] == "succeeded"
    assert client.post(f"/api/payments/{first['id']}/complete").status_code == 409

    second = mobile(client, settle_after_ms=600000).get_json()
    failed = client.post(f"/api/payments/{second['id']}/complete", json={"outcome": "cancelled"}).get_json()
    assert failed["status"] == "failed" and failed["failure"]["code"] == "cancelled"
    assert client.post(f"/api/payments/{second['id']}/complete", json={"outcome": "nope"}).status_code == 409


def test_webhook_payload_and_signature(client, webhooks):
    payment = mobile(client, callback_url="http://hook.test/pay", callback_secret="whsec_x", settle_after_ms=600000).get_json()
    assert webhooks == []  # nothing is sent while pending
    client.post(f"/api/payments/{payment['id']}/complete")
    [hook] = webhooks
    assert hook["url"] == "http://hook.test/pay"
    assert hook["body"]["event"] == "payment.succeeded" and hook["body"]["data"]["id"] == payment["id"]
    assert hook["headers"]["X-Mockbox-Event"] == "payment.succeeded"
    assert hook["headers"]["X-Mockbox-Signature"] == engine.sign("whsec_x", hook["raw"])
    record = client.get(f"/api/payments/{payment['id']}").get_json()["webhooks"]
    assert record[0]["status_code"] == 200 and record[0]["error"] is None


def test_webhook_failure_is_recorded(client, webhooks, monkeypatch):
    def boom(*args):
        raise OSError("connection refused")

    monkeypatch.setattr(engine, "post_json", boom)
    payment = mobile(client, callback_url="http://hook.test/pay", settle_after_ms=0).get_json()
    record = client.get(f"/api/payments/{payment['id']}").get_json()["webhooks"][0]
    assert record["status_code"] is None and "connection refused" in record["error"]


def test_webhook_end_to_end_over_http(client, monkeypatch):
    monkeypatch.setattr(engine, "run_async", lambda fn: fn())
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            received["signature"] = self.headers["X-Mockbox-Signature"]
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/hook"
        payment = mobile(client, callback_url=url, callback_secret="s3cret", settle_after_ms=0).get_json()
    finally:
        server.server_close()
    assert received["signature"] == engine.sign("s3cret", received["body"])
    assert payment["webhooks"][0]["status_code"] == 204


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"provider": "paypal"}, "provider"),
        ({"phone": "12"}, "phone"),
        ({"amount": 0}, "amount"),
        ({"amount": True}, "amount"),
        ({"currency": "dollars"}, "currency"),
        ({"callback_url": "ftp://x"}, "callback_url"),
        ({"settle_after_ms": -1}, "settle_after_ms"),
        ({"simulate": "card_declined"}, "simulate"),
        ({"metadata": []}, "metadata"),
    ],
)
def test_mobile_money_validation(client, webhooks, overrides, message):
    resp = mobile(client, **overrides)
    assert resp.status_code == 400 and message in resp.get_json()["error"]["message"]


# --------------------------------------------------------------------------- cards
def test_card_succeeds(client, webhooks):
    resp = card(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "succeeded" and body["currency"] == "USD"
    assert body["card"] == {"brand": "visa", "last4": "1111", "exp_month": 12, "exp_year": 2099}
    assert "4111111111111111" not in json.dumps(body)


@pytest.mark.parametrize(
    "number,code",
    [("4000000000001000", "card_declined"), ("4000000000002008", "insufficient_funds"),
     ("4000000000003006", "expired_card"), ("4000000000004004", "incorrect_cvc"),
     ("4000000000006009", "processing_error")],
)
def test_card_test_numbers(client, webhooks, number, code):
    body = card(client, card_number=number).get_json()
    assert body["status"] == "failed" and body["failure"]["code"] == code


def test_card_in_the_past_is_expired(client, webhooks):
    assert card(client, exp_year=2001).get_json()["failure"]["code"] == "expired_card"


def test_card_3ds_flow(client, webhooks):
    body = card(client, card_number="4000000000005001").get_json()
    assert body["status"] == "requires_action"
    url = body["next_action"]["authorize_url"]
    approved = client.post(url, json={"result": "approve"}).get_json()
    assert approved["status"] == "succeeded" and "next_action" not in approved
    assert client.post(url).status_code == 409

    denied = card(client, card_number="4000000000005001").get_json()
    assert client.post(denied["next_action"]["authorize_url"], json={"result": "deny"}).get_json()["status"] == "failed"
    assert client.post(denied["next_action"]["authorize_url"], json={"result": "maybe"}).status_code == 400


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"card_number": "4111111111111112"}, "card_number"),
        ({"card_number": None}, "card_number"),
        ({"exp_month": 13}, "exp_month"),
        ({"exp_year": 1999}, "exp_year"),
        ({"cvc": 123}, "cvc"),
    ],
)
def test_card_validation(client, webhooks, overrides, message):
    resp = card(client, **overrides)
    assert resp.status_code == 400 and message in resp.get_json()["error"]["message"]


@pytest.mark.parametrize("number,brand", [("5555555555554444", "mastercard"), ("378282246310005", "amex")])
def test_card_brands(number, brand):
    assert engine.card_brand(number) == brand and engine.luhn_valid(number)


# --------------------------------------------------------------------------- refunds, idempotency, listing
def test_partial_then_full_refund(client, webhooks):
    payment = card(client, amount=100, callback_url="http://hook.test/r").get_json()
    url = f"/api/payments/{payment['id']}/refund"
    first = client.post(url, json={"amount": 40, "reason": "damaged"})
    assert first.status_code == 201
    assert first.get_json()["payment"]["status"] == "partially_refunded"
    assert client.post(url, json={"amount": 70}).status_code == 400
    rest = client.post(url).get_json()
    assert rest["refund"]["amount"] == 60 and rest["payment"]["status"] == "refunded"
    assert client.post(url).status_code == 409
    assert [h["body"]["event"] for h in webhooks] == ["payment.succeeded", "payment.refunded", "payment.refunded"]


def test_cannot_refund_pending(client, webhooks):
    payment = mobile(client).get_json()
    assert client.post(f"/api/payments/{payment['id']}/refund").status_code == 409


def test_idempotency_key_replays(client, webhooks):
    headers = {"Idempotency-Key": "order-42"}
    first = client.post("/api/payments/cards", json=CARD, headers=headers)
    second = client.post("/api/payments/cards", json=CARD, headers=headers)
    assert second.status_code == 200 and second.headers["Idempotent-Replayed"] == "true"
    assert first.get_json()["id"] == second.get_json()["id"]
    assert len(client.get("/api/payments").get_json()) == 1


def test_list_filter_and_reset(client, webhooks):
    card(client)
    card(client, card_number="4000000000001000")
    mobile(client)
    failed = client.get("/api/payments?filter[status]=failed").get_json()
    assert len(failed) == 1 and failed[0]["card"]["last4"] == "1000"
    assert client.delete("/api/payments").get_json() == {"deleted": 3}
    assert client.get("/api/payments").get_json() == []


def test_unknown_payment_and_bad_body(client, webhooks):
    assert client.get("/api/payments/pay_missing").status_code == 404
    resp = client.post("/api/payments/cards", data="[1]", content_type="application/json")
    assert resp.status_code == 400


def test_payments_are_per_app(make_app, webhooks):
    a, b = make_app().test_client(), make_app().test_client()
    card(a)
    assert b.get("/api/payments").get_json() == []
