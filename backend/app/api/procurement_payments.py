from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.core.security import require_authenticated_user
from backend.app.models.auth import User
from backend.app.models.procurement import ProcurementPayment
from backend.app.api.procurement import invoice_access, event, commit
from backend.app.procurement import paypal

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement payments"])


def approval_link(result):
    for link in result.get("links", []):
        url = link.get("href", "")
        if link.get("rel") in {"approve", "payer-action"} and urlsplit(url).hostname == "www.sandbox.paypal.com" and urlsplit(url).scheme == "https":
            return url
    return None


def verify_order(result, invoice):
    try:
        units = result["purchase_units"]
        unit = units[0]
        valid = (len(units) == 1 and unit["payee"]["merchant_id"] == invoice.terms["recipient_id"]
                 and unit["custom_id"] == f"auditai-invoice-{invoice.id}"
                 and unit["amount"]["currency_code"] == "USD"
                 and Decimal(unit["amount"]["value"]) == invoice.stated_total)
    except (KeyError, IndexError, TypeError, InvalidOperation):
        valid = False
    if not valid:
        raise HTTPException(409, "Provider order does not match the reviewed invoice. Payment is paused.")


def reconcile(result, invoice, payment):
    verify_order(result, invoice)
    if result.get("status") == "COMPLETED":
        captures = result["purchase_units"][0].get("payments", {}).get("captures", [])
        try:
            complete = (len(captures) == 1 and captures[0]["status"] == "COMPLETED"
                        and captures[0]["amount"]["currency_code"] == "USD"
                        and Decimal(captures[0]["amount"]["value"]) == invoice.stated_total)
        except (KeyError, TypeError, InvalidOperation):
            complete = False
        if not complete:
            raise HTTPException(409, "Capture evidence is incomplete; reconcile with PayPal before proceeding.")
        invoice.status = "paid"
        payment.status = "completed"
    else:
        payment.status = result.get("status", "unknown").lower()
    payment.provider_result = result


@router.get("/payment-config")
def payment_config(user: User = Depends(require_authenticated_user)):
    return {"configured":paypal.configured(), "environment":"sandbox", "live_payments":False}


@router.post("/invoices/{invoice_id}/checkout")
def checkout(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_authenticated_user)):
    invoice, order, row = invoice_access(db, invoice_id, user)
    if invoice.status != "reviewed":
        raise HTTPException(409, "Invoice must pass matching and independent finance review.")
    if invoice.terms.get("currency") != "USD":
        raise HTTPException(409, "PayPal sandbox checkout supports USD only. This INR purchase can be recorded and audited, but must use an INR-capable payment process.")
    if not paypal.configured():
        raise HTTPException(503, "Configure the PayPal sandbox credentials before checkout.")
    if invoice.terms["recipient_id"] != paypal.configuration()["merchant_id"]:
        raise HTTPException(409, "This recipient is not the configured sandbox merchant.")
    payment = db.query(ProcurementPayment).filter_by(invoice_id=invoice.id).first()
    if not payment:
        payment = ProcurementPayment(invoice_id=invoice.id,create_key=str(uuid4()),capture_key=str(uuid4()),status="creating")
        db.add(payment)
        commit(db)  # persist idempotency keys before a network call can time out
        invoice, order, row = invoice_access(db, invoice_id, user)
    if payment.provider_order_id:
        result = paypal.call("GET", f"/v2/checkout/orders/{payment.provider_order_id}")
        reconcile(result, invoice, payment)
    else:
        if payment.created_at < datetime.utcnow() - timedelta(hours=5):
            raise HTTPException(409, "Unconfirmed checkout is too old to retry safely. Manual reconciliation is required.")
        result = paypal.call("POST", "/v2/checkout/orders", {
            "intent":"CAPTURE", "purchase_units":[{"custom_id":f"auditai-invoice-{invoice.id}",
            "payee":{"merchant_id":invoice.terms["recipient_id"]},
            "amount":{"currency_code":"USD","value":str(invoice.stated_total)}}]}, payment.create_key)
        if not result.get("id"):
            raise HTTPException(502, "PayPal did not return an order ID.")
        payment.provider_order_id = result["id"]
        payment.provider_result = result
        payment.status = result.get("status", "created").lower()
        event(db, row, user, "sandbox_checkout_created", invoice_id=invoice.id)
    commit(db)
    return {"status":payment.status,"approval_url":approval_link(result),"environment":"sandbox"}


@router.post("/invoices/{invoice_id}/payment-status")
def payment_status(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_authenticated_user)):
    invoice, order, row = invoice_access(db, invoice_id, user)
    payment = db.query(ProcurementPayment).filter_by(invoice_id=invoice.id).first()
    if not payment or not payment.provider_order_id:
        return {"status":"not_confirmed", "note":"No provider order ID is available. Do not assume a payment failed."}
    was_paid = invoice.status == "paid"
    result = paypal.call("GET", f"/v2/checkout/orders/{payment.provider_order_id}")
    reconcile(result, invoice, payment)
    if not was_paid and invoice.status == "paid":
        event(db, row, user, "sandbox_payment_confirmed", invoice_id=invoice.id)
    commit(db)
    return {"status":payment.status,"approval_url":approval_link(result),"environment":"sandbox"}


@router.post("/invoices/{invoice_id}/capture")
def capture(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_authenticated_user)):
    invoice, order, row = invoice_access(db, invoice_id, user)
    if invoice.status not in {"reviewed", "paid"}:
        raise HTTPException(409, "Invoice is not eligible for capture.")
    payment = db.query(ProcurementPayment).filter_by(invoice_id=invoice.id).first()
    if not payment or not payment.provider_order_id:
        raise HTTPException(409, "Start sandbox checkout first.")
    result = paypal.call("GET", f"/v2/checkout/orders/{payment.provider_order_id}")
    verify_order(result, invoice)
    if result.get("status") == "APPROVED":
        result = paypal.call("POST", f"/v2/checkout/orders/{payment.provider_order_id}/capture", {}, payment.capture_key)
    elif result.get("status") != "COMPLETED":
        raise HTTPException(409, "Payer approval is required, or payment is still pending. Check status.")
    was_paid = invoice.status == "paid"
    reconcile(result, invoice, payment)
    if not was_paid and invoice.status == "paid":
        event(db, row, user, "sandbox_payment_confirmed", invoice_id=invoice.id)
    commit(db)
    return {"status":payment.status,"environment":"sandbox"}
