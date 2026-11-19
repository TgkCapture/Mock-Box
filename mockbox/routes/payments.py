"""Simulated payments: /api/payments (mobile money and cards). Engine in mockbox/payments.py."""

from functools import wraps

from flask import Blueprint, jsonify, request, url_for

from ..errors import ApiError
from ..listing import respond_with_items
from ..payments import PaymentError, get_payments
from .auth import json_object_body

bp = Blueprint("payments", __name__, url_prefix="/payments")

MAX_IDEMPOTENCY_KEY = 255


def payment_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except PaymentError as exc:
            raise ApiError(exc.status, exc.message) from None

    return wrapped


def _idempotency_key():
    key = request.headers.get("Idempotency-Key")
    if key is not None and not 1 <= len(key) <= MAX_IDEMPOTENCY_KEY:
        raise ApiError(400, f"Idempotency-Key must be 1..{MAX_IDEMPOTENCY_KEY} characters")
    return key


def _created(payment, replayed: bool):
    status = 200 if replayed else (202 if payment["status"] == "pending" else 201)
    headers = {"Location": url_for(".get_payment", payment_id=payment["id"])}
    if replayed:
        headers["Idempotent-Replayed"] = "true"
    return jsonify(payment), status, headers


@bp.get("")
@payment_errors
def list_payments():
    return respond_with_items(get_payments().list())


@bp.delete("")
def reset_payments():
    return jsonify({"deleted": get_payments().reset()})


@bp.post("/mobile-money")
@payment_errors
def create_mobile_money():
    return _created(*get_payments().create_mobile_money(json_object_body(), _idempotency_key()))


@bp.post("/cards")
@payment_errors
def create_card():
    return _created(*get_payments().create_card(json_object_body(), _idempotency_key()))


@bp.get("/<payment_id>")
@payment_errors
def get_payment(payment_id):
    return jsonify(get_payments().get(payment_id))


@bp.post("/<payment_id>/complete")
@payment_errors
def complete_payment(payment_id):
    return jsonify(get_payments().complete(payment_id, json_object_body().get("outcome")))


@bp.post("/<payment_id>/authorize")
@payment_errors
def authorize_payment(payment_id):
    result = json_object_body().get("result", "approve")
    if result not in ("approve", "deny"):
        raise ApiError(400, "result must be 'approve' or 'deny'")
    return jsonify(get_payments().authorize(payment_id, result == "approve"))


@bp.post("/<payment_id>/refund")
@payment_errors
def refund_payment(payment_id):
    refund, payment = get_payments().refund(payment_id, json_object_body())
    return jsonify({"refund": refund, "payment": payment}), 201
