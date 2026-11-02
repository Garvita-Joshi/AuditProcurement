"""Seed three clearly labeled approval-workflow examples in a local database.

Run from the repository root with ``python -m scripts.seed_procurement_demo``.
The script is additive and idempotent: it never deletes records or changes the
role of an existing user. Do not point it at a shared or production database.
"""
from datetime import datetime, timedelta
from urllib.parse import urlparse

from backend.app.api.procurement import (
    _approval_steps,
    _sync_legacy_workflow,
    create_request,
)
from backend.app.db import DATABASE_URL, SessionLocal
from backend.app.models.auth import User
from backend.app.models.procurement import (
    ApprovalStep,
    ApprovalSubtask,
    ProcurementContext,
    ProcurementNotification,
    PurchaseRequest,
)
from backend.app.procurement.contracts import RequestCreate


def _require_local_database():
    parsed = urlparse(DATABASE_URL)
    if DATABASE_URL.startswith("sqlite:"):
        return
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Refusing to seed a non-local database. Set DATABASE_URL to a local database first.")


def _get_or_create_user(db, email, name, role):
    user = db.query(User).filter_by(email=email).first()
    if user:
        if not user.is_active:
            user.is_active = True
        return user
    user = User(email=email, full_name=name, role=role, is_active=True)
    db.add(user)
    db.flush()
    return user


def _payload(title, budget, currency, sku, description, price, *, department, category,
             purpose, shares_personal_data=False, data_types=None, data_usage=""):
    return RequestCreate.model_validate({
        "title": title,
        "budget_limit": budget,
        "details": {
            "department": department,
            "category": category,
            "purpose": purpose,
            "shares_personal_data": shares_personal_data,
            "data_types": data_types or [],
            "data_usage": data_usage,
        },
        "terms": {
            "supplier_id": "demo-supplier",
            "recipient_id": "demo-recipient",
            "currency": currency,
            "items": [{"sku": sku, "description": description, "quantity": 1, "unit_price": price}],
            "delivery": "0.00",
            "tax": "0.00",
        },
    })


def _create_if_missing(db, requester, payload):
    existing = db.query(PurchaseRequest).filter_by(requester_id=requester.id, title=payload.title).first()
    if existing:
        return existing
    create_request(payload, db, requester)
    db.flush()
    return db.query(PurchaseRequest).filter_by(requester_id=requester.id, title=payload.title).first()


def _set_stage(db, row, users, approved_count, current_role):
    """Set an example to a deterministic point in its chain, idempotently."""
    steps = db.query(ApprovalStep).filter_by(request_id=row.id).order_by(ApprovalStep.step_order).all()
    now = datetime.utcnow()
    for step in steps:
        step.assignee_id = users[step.role].id
        for subtask in db.query(ApprovalSubtask).filter_by(step_id=step.id).all():
            subtask.assignee_id = users["admin"].id
        if step.step_order <= approved_count:
            step.status = "approved"
            step.started_at = step.started_at or now - timedelta(days=1)
            step.decision = {
                "outcome": "approved",
                "decided_by": users[step.role].id,
                "decided_at": (now - timedelta(hours=2)).isoformat(),
                "reason": "Demo record: prior reviewer completed this step.",
            }
            for subtask in db.query(ApprovalSubtask).filter_by(step_id=step.id).all():
                subtask.status = "done"
        elif step.role == current_role:
            step.status = "ready"
            step.started_at = step.started_at or now
            step.decision = {}
        else:
            step.status = "not_started"
            step.started_at = None
            step.decision = {}

    current = next((step for step in steps if step.role == current_role and step.status == "ready"), None)
    if current:
        already_notified = db.query(ProcurementNotification).filter_by(
            request_id=row.id, step_id=current.id, user_id=current.assignee_id
        ).first()
        if not already_notified:
            db.add(ProcurementNotification(
                user_id=current.assignee_id,
                request_id=row.id,
                step_id=current.id,
                title="Approval ready",
                message=f"{current.name} is ready for request PR-{row.id:04d}.",
            ))
    ctx = db.get(ProcurementContext, row.id)
    if ctx:
        _sync_legacy_workflow(db, ctx, row.id)


def main():
    _require_local_database()
    db = SessionLocal()
    try:
        users = {
            "requester": _get_or_create_user(db, "demo.requester@auditai.local", "Demo Requester", "auditor"),
            "manager": _get_or_create_user(db, "demo.manager@auditai.local", "Demo Manager", "manager"),
            "admin": _get_or_create_user(db, "demo.procurement@auditai.local", "Demo Procurement Admin", "admin"),
            "finance": _get_or_create_user(db, "demo.finance@auditai.local", "Demo Finance Reviewer", "finance"),
            "security": _get_or_create_user(db, "demo.security@auditai.local", "Demo Security Reviewer", "security"),
        }
        db.flush()

        examples = [
            (_payload(
                "[Demo] INR laptop purchase — manager intake",
                "60000.00", "INR", "DEMO-LAPTOP-01", "Engineering laptop", "45000.00",
                department="Engineering", category="IT hardware",
                purpose="Replace an aging engineering laptop for a new team member.",
            ), 0, "manager"),
            (_payload(
                "[Demo] Cloud support service — procurement review",
                "150000.00", "INR", "DEMO-CLOUD-01", "Annual cloud support service", "120000.00",
                department="IT", category="IT services",
                purpose="Annual cloud support and maintenance for production services.",
            ), 1, "admin"),
            (_payload(
                "[Demo] HR platform — finance review",
                "90000.00", "INR", "DEMO-HR-01", "HR platform annual subscription", "82000.00",
                department="Human Resources", category="Software and licences",
                purpose="Manage employee onboarding and HR records.",
                shares_personal_data=True,
                data_types=["Personal Data (e.g. name, email, location, etc.)"],
                data_usage="The supplier will host employee profiles and provide HR workflow access.",
            ), 2, "finance"),
        ]

        titles = []
        for payload, approved_count, current_role in examples:
            row = _create_if_missing(db, users["requester"], payload)
            _set_stage(db, row, users, approved_count, current_role)
            titles.append((row.id, row.title, current_role))
        db.commit()
        for request_id, title, current_role in titles:
            print(f"PR-{request_id:04d}: {title} — awaiting {current_role}")
        print("Demo workflow data is ready. Seeded users are local examples; OTP/login policy is unchanged.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
