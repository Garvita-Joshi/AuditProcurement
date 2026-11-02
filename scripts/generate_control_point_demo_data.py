"""Create a safe, deterministic ledger for demonstrating AuditAI Control Points.

The generated CSV is intentionally separate from existing project datasets.  It
contains normal business activity plus labelled examples of each important
fraud/error pattern, making it suitable for a demo, UI walkthrough, or test.
"""
from __future__ import annotations

import random
from datetime import date, time, timedelta
from pathlib import Path

import pandas as pd


RNG = random.Random(240)
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "control_point_demo_ledger.csv"
VENDORS = ("Northstar Office", "Metro Logistics", "Apex Cloud", "Harbor Utilities")
ACCOUNTS = ("Office Supplies", "Logistics", "IT Infrastructure", "Utilities")


def record(number: int, when: date, vendor: str, amount: float, account: str, **extra) -> dict:
    row = {
        "txn_id": f"DEMO-{number:04d}",
        "date": when.isoformat(),
        "time": "11:30:00",
        "vendor_name": vendor,
        "amount": round(amount, 2),
        "account_head": account,
        "payment_method": "NEFT",
        "entry_method": "system",
        "created_by": "Asha Rao",
        "approved_by": "Vikram Shah",
        "invoice_number": f"INV-{number:04d}",
        "description": "Routine approved business purchase",
        "fraud_type": "none",
        "is_fraud": False,
    }
    row.update(extra)
    return row


def generate() -> pd.DataFrame:
    start = date(2026, 1, 1)
    rows = []
    # 120 ordinary transactions create a useful history for frequency, percentile,
    # two-digit Benford, and account-baseline controls.
    for number in range(1, 121):
        rows.append(record(
            number, start + timedelta(days=number % 75), RNG.choice(VENDORS),
            RNG.uniform(1_000, 22_000), RNG.choice(ACCOUNTS),
        ))

    rows.extend([
        record(121, date(2026, 3, 19), "Metro Logistics", 24_500, "Logistics", fraud_type="duplicate_payment", is_fraud=True, invoice_number="DUP-901"),
        record(122, date(2026, 3, 21), "Metro Logistics", 24_500, "Logistics", fraud_type="duplicate_payment", is_fraud=True, invoice_number="DUP-902"),
        record(123, date(2026, 3, 22), "Threshold Vendor", 29_000, "Office Supplies", fraud_type="split_invoice", is_fraud=True),
        record(124, date(2026, 3, 23), "Threshold Vendor", 29_000, "Office Supplies", fraud_type="split_invoice", is_fraud=True),
        record(125, date(2026, 3, 25), "Shell Offshore Services", 500_000, "Consulting Fees", entry_method="manual", description="Urgent adjustment for offshore related entity", payment_method="Cash", fraud_type="manual_journal_vendor_fraud", is_fraud=True),
        record(126, date(2026, 3, 31), "New Revenue Partner", 900_000, "Revenue", entry_method="manual", description="Period-end revenue adjustment", fraud_type="revenue_cutoff", is_fraud=True),
        record(127, date(2026, 3, 28), "City Restaurant", 18_500, "Travel & Entertainment", description="Personal family restaurant reimbursement", fraud_type="personal_expense", is_fraud=True),
        record(128, date(2026, 3, 29), "Unknown Employee", 180_000, "Payroll", entry_method="manual", description="Manual payroll adjustment", fraud_type="payroll_anomaly", is_fraud=True),
        record(129, date(2026, 3, 30), "Apex Cloud", 75_000, "IT Infrastructure", description="Credit note reversal for prior invoice", fraud_type="reversal", is_fraud=True),
        record(130, date(2026, 3, 31), "Ghost Vendor Pvt Ltd", 85_000, "Consulting Fees", description="One-time urgent service", fraud_type="ghost_vendor", is_fraud=True),
    ])
    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = generate()
    frame.to_csv(OUTPUT, index=False)
    print(f"Created {OUTPUT} with {len(frame)} entries and {int(frame.is_fraud.sum())} labelled risk entries.")
