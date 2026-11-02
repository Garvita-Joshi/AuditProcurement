from pydantic import BaseModel, Field
from datetime import date, time
from typing import Optional
from decimal import Decimal

# --- Vendor Schemas ---
class VendorBase(BaseModel):
    vendor_name: str
    gstin: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    bank_account: Optional[str] = None
    status: str = "Approved"
    registration_date: Optional[date] = None

class VendorCreate(VendorBase):
    pass

class Vendor(VendorBase):
    class Config:
        from_attributes = True


# --- Transaction Schemas ---
class TransactionBase(BaseModel):
    txn_id: str
    date: date
    time: Optional[time] = None
    vendor_name: str
    amount: Decimal
    payment_method: Optional[str] = None
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    account_head: Optional[str] = None
    is_fraud: bool = False
    fraud_type: str = "none"

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int

    class Config:
        from_attributes = True
