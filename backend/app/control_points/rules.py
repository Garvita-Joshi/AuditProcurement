"""Deterministic controls. Each rule is explainable without a black-box model."""
from collections import Counter
from datetime import timedelta
from decimal import Decimal
import math
import re
from .framework import Category, Status, result

KEYWORDS = ("adjustment", "misc", "personal", "reimburse", "cash", "urgent", "one-time")

def _amount(t): return float(t.amount or 0)
def _days(a, b): return abs((a.date - b.date).days)
def _tokens(value): return {p for p in re.split(r"[^a-z]+", (value or "").lower()) if len(p) >= 3}

class BaseControl:
    def __init__(self, control_id, name, description, category):
        self.id, self.name, self.description, self.category = control_id, name, description, category

class DuplicateEntry(BaseControl):
    def __init__(self, days=90): super().__init__("duplicate_entry", "Duplicate Entry", "Detects matching payee, amount, and date-window entries.", Category.STRUCTURAL); self.days=days
    def evaluate(self, tx, ctx):
        matches=[o for o in ctx if o.id != tx.id and o.vendor_name==tx.vendor_name and _amount(o)==_amount(tx) and _days(o,tx)<=self.days]
        return result(self, Status.FAIL_HIGH if matches else Status.PASS, 94 if matches else 0, f"{len(matches)} matching entry/entries found within {self.days} days." if matches else "No matching amount-payee entry found in the configured window.", matched_transaction_ids=[o.txn_id for o in matches])

class SplitInvoice(BaseControl):
    def __init__(self, threshold=50000, days=3): super().__init__("split_invoice", "Split Invoice", "Detects clustered sub-threshold payments that bypass an approval limit.", Category.STRUCTURAL); self.threshold,self.days=threshold,days
    def evaluate(self, tx, ctx):
        group=[o for o in ctx if o.vendor_name==tx.vendor_name and _days(o,tx)<=self.days and _amount(o)<self.threshold]
        total=sum(_amount(o) for o in group)
        hit=len(group)>=2 and total>=self.threshold
        return result(self, Status.FAIL_HIGH if hit else Status.PASS, min(95, 55+len(group)*12) if hit else 0, f"{len(group)} sub-threshold payments total {total:,.2f} within {self.days} days." if hit else "No clustered sub-threshold payments exceed the approval threshold.", transaction_ids=[o.txn_id for o in group], threshold=self.threshold, total=total)

class RoundNumber(BaseControl):
    def __init__(self): super().__init__("round_number", "Round Number / Last Digits", "Highlights unusually rounded payment values.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        amount=_amount(tx); cents=round(amount%1,2); thousand=amount>=1000 and amount%1000==0
        hit=thousand or cents in (0, .99)
        level=Status.FAIL_MEDIUM if thousand else Status.FAIL_LOW if hit else Status.PASS
        return result(self, level, 76 if thousand else 48 if hit else 0, "Amount is a large exact thousand." if thousand else "Amount ends in a commonly rounded pricing suffix." if hit else "Amount does not use a suspicious round-number pattern.", amount=amount)

class ManualEntry(BaseControl):
    def __init__(self): super().__init__("manual_entry", "Manual Entry", "Flags entries manually created outside an automated source feed.", Category.BEHAVIORAL)
    def evaluate(self, tx, ctx):
        manual=(tx.entry_method or "").lower() in {"manual","journal","user"}
        return result(self, Status.FAIL_MEDIUM if manual else Status.PASS, 72 if manual else 0, "Entry method is marked manual and needs supporting evidence." if manual else "Entry is not marked as manually entered.", entry_method=tx.entry_method)

class SequenceGap(BaseControl):
    def __init__(self): super().__init__("sequence_gap", "Sequence Gap", "Finds gaps in numeric invoice references for the same vendor.", Category.STRUCTURAL)
    def evaluate(self, tx, ctx):
        ref=tx.invoice_number or tx.txn_id; m=re.search(r"(\d+)$",ref or "")
        if not m: return result(self, Status.PASS, 0, "No numeric invoice sequence is available for this entry.")
        nums=[]
        for o in ctx:
            n=re.search(r"(\d+)$",(o.invoice_number or o.txn_id or ""))
            if o.vendor_name==tx.vendor_name and n: nums.append(int(n.group(1)))
        current=int(m.group(1)); gap=(current-1 not in nums and current+1 not in nums and len(nums)>1)
        return result(self, Status.FAIL_LOW if gap else Status.PASS, 45 if gap else 0, "This reference is isolated from neighbouring vendor sequence numbers." if gap else "Reference sequence has neighbouring entries or insufficient history.", reference=ref)

class SuspiciousKeyword(BaseControl):
    def __init__(self, keywords=KEYWORDS): super().__init__("suspicious_keyword", "Suspicious Keyword", "Flags configurable terms that require a reviewer explanation.", Category.BEHAVIORAL); self.keywords=tuple(keywords)
    def evaluate(self, tx, ctx):
        text=" ".join(filter(None,[tx.description, tx.payment_method] )).lower(); found=[k for k in self.keywords if k in text]
        return result(self, Status.FAIL_MEDIUM if found else Status.PASS, min(90,55+len(found)*10) if found else 0, f"Review keyword(s) found: {', '.join(found)}." if found else "No configured review keyword appears in the entry text.", keywords=found)

class WeekendAfterHours(BaseControl):
    def __init__(self, start=9, end=18): super().__init__("weekend_after_hours", "Weekend / After-hours", "Flags entries posted outside normal business hours.", Category.TEMPORAL); self.start,self.end=start,end
    def evaluate(self, tx, ctx):
        weekend=tx.date.weekday()>=5; after=tx.time is not None and not self.start<=tx.time.hour<self.end; hit=weekend or after
        return result(self, Status.FAIL_LOW if hit else Status.PASS, 55 if weekend else 42 if after else 0, "Posted on a weekend." if weekend else "Posted outside configured business hours." if after else "Posted during a business day and normal hours.", weekend=weekend, after_hours=after)

class ZeroEmpty(BaseControl):
    def __init__(self): super().__init__("zero_empty_entry", "Zero / Empty Entry", "Detects missing counterparty, account, or non-positive value.", Category.STRUCTURAL)
    def evaluate(self, tx, ctx):
        missing=[name for name,val in (("amount",_amount(tx)>0),("vendor",bool(tx.vendor_name)),("account",bool(tx.account_head))) if not val]
        return result(self, Status.FAIL_HIGH if missing else Status.PASS, 98 if missing else 0, f"Required field(s) missing or invalid: {', '.join(missing)}." if missing else "Required amount, payee, and account fields are populated.", missing_fields=missing)

class GhostVendor(BaseControl):
    def __init__(self, threshold=25000): super().__init__("ghost_vendor", "Ghost Vendor", "Flags high-value payments to a vendor with no earlier activity.", Category.RELATED_PARTY); self.threshold=threshold
    def evaluate(self, tx, ctx):
        prior=[o for o in ctx if o.vendor_name==tx.vendor_name and o.date<tx.date]; hit=not prior and _amount(tx)>=self.threshold
        return result(self, Status.FAIL_MEDIUM if hit else Status.PASS, 78 if hit else 0, "First known vendor payment exceeds the review threshold." if hit else "Vendor has history or the payment is below the first-use threshold.", prior_count=len(prior), threshold=self.threshold)

class RareFlow(BaseControl):
    def __init__(self, cutoff=0.05): super().__init__("rare_flow", "Rare Flow", "Identifies rare account-to-counterparty pairings in this ledger.", Category.STATISTICAL); self.cutoff=cutoff
    def evaluate(self, tx, ctx):
        pairs=Counter((o.account_head,o.vendor_name) for o in ctx); count=pairs[(tx.account_head,tx.vendor_name)]; total=max(1,len(ctx)); rate=count/total; hit=len(ctx)>=20 and rate<=self.cutoff
        return result(self, Status.FAIL_LOW if hit else Status.PASS, max(35,80-rate*1000) if hit else 0, f"This account-payee pairing occurs {count} time(s) in {total} entries." if hit else "Account-payee pairing is not rare for the available history.", frequency=count, population=total, rate=round(rate,4))

class RelatedParty(BaseControl):
    def __init__(self): super().__init__("related_party", "Related Party", "Flags meaningful name overlap between the preparer and payee.", Category.RELATED_PARTY)
    def evaluate(self, tx, ctx):
        matched=sorted(_tokens(tx.created_by)&_tokens(tx.vendor_name)); hit=bool(matched)
        return result(self, Status.FAIL_HIGH if hit else Status.PASS, 88 if hit else 0, f"Payee and preparer share term(s): {', '.join(matched)}." if hit else "No meaningful preparer-payee name overlap found.", matched_terms=matched)

class BenfordDeviation(BaseControl):
    def __init__(self): super().__init__("benford_first_digit", "Benford First Digit", "Shows whether this entry contributes to a leading-digit population deviation.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        digits=[int(str(int(abs(_amount(o)))).lstrip("0")[0]) for o in ctx if _amount(o)>=1]
        if len(digits)<30: return result(self, Status.PASS,0,"At least 30 entries are required before using this population-level control.", population=len(digits))
        digit=int(str(int(abs(_amount(tx)))).lstrip("0")[0]); observed=digits.count(digit)/len(digits); expected=math.log10(1+1/digit); deviation=abs(observed-expected)/expected
        hit=deviation>.35
        return result(self, Status.FAIL_LOW if hit else Status.PASS, min(85,deviation*100) if hit else 0, f"Leading digit {digit} occurs {observed:.1%} versus Benford expectation {expected:.1%}." if hit else "This leading digit is within the configured population tolerance.", digit=digit, observed=observed, expected=expected)


class CashExpenditure(BaseControl):
    def __init__(self): super().__init__("cash_expenditure", "Cash Expenditure", "Flags cash payments because they typically have weaker traceability.", Category.BEHAVIORAL)
    def evaluate(self, tx, ctx):
        hit=(tx.payment_method or "").lower()=="cash"
        return result(self, Status.FAIL_MEDIUM if hit else Status.PASS, 68 if hit else 0, "Transaction is paid in cash and requires supporting evidence." if hit else "Payment is not recorded as cash.", payment_method=tx.payment_method)

class ComplexInstrument(BaseControl):
    terms=("hedge","derivative","swap","option","forward","structured note")
    def __init__(self): super().__init__("complex_instrument", "Complex Instrument", "Flags entries whose wording indicates a complex financial instrument.", Category.BEHAVIORAL)
    def evaluate(self, tx, ctx):
        text=(getattr(tx,"description",None) or "").lower(); found=[term for term in self.terms if term in text]
        return result(self, Status.FAIL_MEDIUM if found else Status.PASS, 74 if found else 0, f"Complex-instrument term(s) found: {', '.join(found)}." if found else "No complex-instrument wording was found.", matched_terms=found)

class ComplexStructure(BaseControl):
    terms=("offshore","shell","special purpose","related entity","intercompany","trust")
    def __init__(self): super().__init__("complex_structure", "Complex Structure", "Flags wording that can indicate opaque ownership or entity structures.", Category.RELATED_PARTY)
    def evaluate(self, tx, ctx):
        text=" ".join((getattr(tx,"description",None) or "", tx.vendor_name or "")).lower(); found=[term for term in self.terms if term in text]
        return result(self, Status.FAIL_HIGH if found else Status.PASS, 84 if found else 0, f"Complex-structure term(s) found: {', '.join(found)}." if found else "No opaque-structure indicators were found.", matched_terms=found)

class PeriodEndEntry(BaseControl):
    def __init__(self, days=5): super().__init__("end_of_period", "End of Analysis Period", "Flags entries posted near the end of the available analysis period.", Category.TEMPORAL); self.days=days
    def evaluate(self, tx, ctx):
        end=max((o.date for o in ctx), default=tx.date); delta=(end-tx.date).days; hit=0<=delta<self.days
        return result(self, Status.FAIL_LOW if hit else Status.PASS, 52 if hit else 0, f"Posted {delta} day(s) before the analysis-period end." if hit else "Not posted near the end of the available analysis period.", analysis_end=end.isoformat(), days_from_end=delta)

class RevenuePeriodEnd(BaseControl):
    def __init__(self): super().__init__("revenue_period_end", "Revenue Period-End", "Flags revenue entries near period end for cut-off review.", Category.TEMPORAL)
    def evaluate(self, tx, ctx):
        revenue="revenue" in (tx.account_head or "").lower(); end=max((o.date for o in ctx), default=tx.date); hit=revenue and (end-tx.date).days<5
        return result(self, Status.FAIL_MEDIUM if hit else Status.PASS, 70 if hit else 0, "Revenue entry was posted near period end; validate recognition cut-off." if hit else "No period-end revenue cut-off indicator.", account=tx.account_head)

class HighMonetaryValue(BaseControl):
    def __init__(self): super().__init__("high_monetary_value", "High Monetary Value", "Flags entries in the upper tail of monetary values for the ledger.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        values=sorted(_amount(o) for o in ctx if _amount(o)>0)
        if len(values)<20:return result(self,Status.PASS,0,"At least 20 entries are needed for a high-value percentile test.",population=len(values))
        cutoff=values[max(0,math.ceil(len(values)*.98)-1)]; hit=_amount(tx)>=cutoff
        return result(self,Status.FAIL_HIGH if hit else Status.PASS,82 if hit else 0,f"Amount is in the top 2% of ledger values (threshold {cutoff:,.2f})." if hit else "Amount is below the top-2% monetary threshold.",threshold=cutoff)

class UnusualAmount(BaseControl):
    def __init__(self): super().__init__("unusual_amount", "Unusual Amount", "Compares an amount with typical values in the same account.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        values=[_amount(o) for o in ctx if o.account_head==tx.account_head and _amount(o)>0]
        if len(values)<10:return result(self,Status.PASS,0,"Insufficient same-account history for an amount comparison.",population=len(values))
        mean=sum(values)/len(values); std=(sum((x-mean)**2 for x in values)/len(values))**.5; z=abs(_amount(tx)-mean)/(std or 1); hit=z>=2.5
        return result(self,Status.FAIL_MEDIUM if hit else Status.PASS,min(90,z*25) if hit else 0,f"Amount is {z:.1f} standard deviations from the {tx.account_head} mean." if hit else "Amount is within the expected same-account range.",z_score=round(z,2),account_mean=round(mean,2))

class FlowAnalysis(BaseControl):
    def __init__(self): super().__init__("flow_analysis", "Flow Analysis", "Flags unusually large flows for an account-to-payee relationship.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        flows=[_amount(o) for o in ctx if o.account_head==tx.account_head and o.vendor_name==tx.vendor_name]
        if len(flows)<3:return result(self,Status.PASS,0,"Insufficient relationship history for flow analysis.",population=len(flows))
        baseline=sum(flows)/len(flows); hit=_amount(tx)>baseline*3 and _amount(tx)>10000
        return result(self,Status.FAIL_MEDIUM if hit else Status.PASS,75 if hit else 0,f"Amount is {_amount(tx)/baseline:.1f}× the usual account-payee flow." if hit else "Amount is consistent with the account-payee flow history.",baseline=round(baseline,2))

class TwoDigitBenford(BaseControl):
    def __init__(self): super().__init__("benford_two_digit", "2 Digit Benford", "Compares the entry's first two digits with population-level Benford expectations.", Category.STATISTICAL)
    def evaluate(self, tx, ctx):
        prefixes=[str(int(_amount(o)))[:2] for o in ctx if _amount(o)>=10]
        if len(prefixes)<50:return result(self,Status.PASS,0,"At least 50 entries are required for a two-digit Benford test.",population=len(prefixes))
        prefix=str(int(_amount(tx)))[:2]; actual=prefixes.count(prefix)/len(prefixes); expected=math.log10(1+1/int(prefix)); deviation=abs(actual-expected)/(expected or 1); hit=deviation>.5
        return result(self,Status.FAIL_LOW if hit else Status.PASS,min(80,deviation*100) if hit else 0,f"First-two-digit prefix {prefix}: {actual:.1%} observed vs {expected:.1%} expected." if hit else "Two-digit prefix is within the population tolerance.",prefix=prefix,observed=actual,expected=expected)

class EmptyTextField(BaseControl):
    def __init__(self): super().__init__("empty_text_field", "Empty Text Field", "Flags entries without a description or memo.", Category.STRUCTURAL)
    def evaluate(self, tx, ctx):
        hit=not bool((getattr(tx,"description",None) or "").strip())
        return result(self,Status.FAIL_LOW if hit else Status.PASS,46 if hit else 0,"Description/memo is blank and needs corroborating evidence." if hit else "Description/memo is present.")

class Reversal(BaseControl):
    def __init__(self): super().__init__("reversal", "Reversal", "Identifies reversal or credit-note wording that should be tied to an original entry.", Category.STRUCTURAL)
    def evaluate(self, tx, ctx):
        text=(getattr(tx,"description",None) or "").lower(); hit=any(term in text for term in ("reversal","reverse","credit note","void"))
        return result(self,Status.FAIL_LOW if hit else Status.PASS,58 if hit else 0,"Entry is marked as a reversal; confirm the linked original entry." if hit else "Entry is not marked as a reversal.")

class PersonalExpense(BaseControl):
    terms=("personal","restaurant","movie","holiday","family","grocery")
    def __init__(self): super().__init__("personal_expense", "Personal Expense Indicator", "Flags descriptions consistent with personal or non-business expenditure.", Category.BEHAVIORAL)
    def evaluate(self, tx, ctx):
        text=(getattr(tx,"description",None) or "").lower(); found=[x for x in self.terms if x in text]
        return result(self,Status.FAIL_HIGH if found else Status.PASS,86 if found else 0,f"Potential personal-expense term(s): {', '.join(found)}." if found else "No configured personal-expense indicator found.",matched_terms=found)

class PayrollAnomaly(BaseControl):
    def __init__(self): super().__init__("payroll_anomaly", "Payroll Anomaly", "Flags unusual manual payroll entries for reviewer validation.", Category.BEHAVIORAL)
    def evaluate(self, tx, ctx):
        payroll="payroll" in (tx.account_head or "").lower(); manual=(getattr(tx,"entry_method",None) or "").lower()=="manual"; hit=payroll and manual
        return result(self,Status.FAIL_HIGH if hit else Status.PASS,80 if hit else 0,"Manual payroll posting; validate employee master and authorization." if hit else "No manual-payroll indicator.")

def build_default_controls():
    # Values live in config/environment so audit teams can tune controls without rewriting rule logic.
    from backend.app.config import (CONTROL_APPROVAL_THRESHOLD, CONTROL_DUPLICATE_WINDOW_DAYS, CONTROL_GHOST_VENDOR_THRESHOLD, CONTROL_KEYWORDS, CONTROL_SPLIT_WINDOW_DAYS)
    return (DuplicateEntry(CONTROL_DUPLICATE_WINDOW_DAYS), SplitInvoice(CONTROL_APPROVAL_THRESHOLD, CONTROL_SPLIT_WINDOW_DAYS), RoundNumber(), ManualEntry(), SequenceGap(), SuspiciousKeyword(CONTROL_KEYWORDS), WeekendAfterHours(), ZeroEmpty(), GhostVendor(CONTROL_GHOST_VENDOR_THRESHOLD), RareFlow(), RelatedParty(), BenfordDeviation(), CashExpenditure(), ComplexInstrument(), ComplexStructure(), PeriodEndEntry(), RevenuePeriodEnd(), HighMonetaryValue(), UnusualAmount(), FlowAnalysis(), TwoDigitBenford(), EmptyTextField(), Reversal(), PersonalExpense(), PayrollAnomaly())
DEFAULT_CONTROLS=build_default_controls()
