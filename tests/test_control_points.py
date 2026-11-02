from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from backend.app.control_points.rules import DuplicateEntry, SplitInvoice, SuspiciousKeyword, WeekendAfterHours, ZeroEmpty, GhostVendor, RareFlow


def tx(id, **kwargs):
    defaults=dict(id=id,txn_id=f"TXN-{id}",date=date(2026,1,5),time=time(11),vendor_name="Acme Supplies",amount=Decimal("1000"),account_head="Office",description="normal purchase",entry_method="system",created_by="Riya Shah",payment_method="NEFT",invoice_number=f"INV-{id}")
    defaults.update(kwargs); return SimpleNamespace(**defaults)

def test_duplicate_entry_fires_and_clean_entry_passes():
    first=tx(1); duplicate=tx(2,date=date(2026,1,8)); clean=tx(3,amount=Decimal("1001"))
    assert DuplicateEntry().evaluate(duplicate,[first,duplicate]).status.value == "fail_high"
    assert DuplicateEntry().evaluate(clean,[first,clean]).status.value == "pass"

def test_split_invoice_fires():
    a=tx(1,amount=Decimal("30000")); b=tx(2,amount=Decimal("30000"),date=date(2026,1,7))
    assert SplitInvoice(threshold=50000,days=3).evaluate(b,[a,b]).status.value == "fail_high"

def test_keyword_temporal_empty_and_ghost_controls():
    suspicious=tx(1,description="urgent cash adjustment",date=date(2026,1,3),amount=Decimal("40000"))
    assert SuspiciousKeyword().evaluate(suspicious,[suspicious]).status.value == "fail_medium"
    assert WeekendAfterHours().evaluate(suspicious,[suspicious]).status.value == "fail_low"
    assert GhostVendor().evaluate(suspicious,[suspicious]).status.value == "fail_medium"
    broken=tx(2,amount=Decimal("0"),account_head="")
    assert ZeroEmpty().evaluate(broken,[broken]).status.value == "fail_high"

def test_rare_flow_needs_a_meaningful_population():
    population=[tx(i,vendor_name="Frequent",account_head="Office") for i in range(1,30)]
    rare=tx(99,vendor_name="Rare",account_head="Legal")
    assert RareFlow().evaluate(rare,population+[rare]).status.value == "fail_low"
