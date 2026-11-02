"""Explicit additive initialization: python -m scripts.init_procurement.

Creates the procurement tables additively. Missing authentication tables are created first. Does not change or drop existing tables; no startup migration.
"""
from backend.app.db import engine
from backend.app.api.sourcing import SourcingRequest, SourcingSearch
from backend.app.models.auth import User, OtpChallenge, RefreshSession
from backend.app.models.procurement import (PurchaseRequest, PurchaseOrder, SupplierInvoice, ProcurementContext, ProcurementEvent, ProcurementDocument, InvoiceRevision, ProcurementPayment, ApprovalStep, ApprovalSubtask, ProcurementNotification)

if __name__ == "__main__":
    for model in (User, SourcingRequest, SourcingSearch, OtpChallenge, RefreshSession, PurchaseRequest, PurchaseOrder, SupplierInvoice, ProcurementContext, ProcurementEvent, ProcurementDocument, InvoiceRevision, ProcurementPayment, ApprovalStep, ApprovalSubtask, ProcurementNotification):
        model.__table__.create(engine, checkfirst=True)
    print("Procurement foundation tables ready.")
