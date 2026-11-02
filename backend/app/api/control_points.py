"""Control Point evaluation, assertion-risk, trend, and ledger upload APIs."""
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import Any
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from backend.app.control_points.framework import Status
from backend.app.control_points.rules import DEFAULT_CONTROLS
from backend.app.db import Base, engine, get_db
from backend.app.config import RATIO_DEFINITIONS
from backend.app.models.control import ControlPointAssertionMap, ControlPointResult, IngestionBatch
from backend.app.models.transaction import Transaction, Vendor
from backend.app.models.expense import ExpenseClaim
from backend.app.control_points.claim_rules import CLAIM_CONTROLS

router=APIRouter(prefix="/api/v1", tags=["Control Points"])
RISK_ORDER={"fail_high":0,"fail_medium":1,"fail_low":2,"pass":3}
ASSERTIONS=("existence_occurrence","rights_obligations","completeness","valuation_accuracy","presentation_classification","cut_off")
DEFAULT_MAP={
 "duplicate_entry":(("existence_occurrence",.9),("valuation_accuracy",.6)), "split_invoice":(("completeness",.6),("presentation_classification",.7)),
 "round_number":(("valuation_accuracy",.5),), "manual_entry":(("existence_occurrence",.6),("rights_obligations",.5)),
 "sequence_gap":(("completeness",.8),), "suspicious_keyword":(("presentation_classification",.5),),
 "weekend_after_hours":(("cut_off",.7),), "zero_empty_entry":(("completeness",.9),),
 "ghost_vendor":(("existence_occurrence",.8),("rights_obligations",.6)), "rare_flow":(("presentation_classification",.5),),
 "related_party":(("rights_obligations",.9),("existence_occurrence",.6)), "benford_first_digit":(("valuation_accuracy",.6),),
 "cash_expenditure":(("existence_occurrence",.5),), "complex_instrument":(("valuation_accuracy",.7),("presentation_classification",.6)),
 "complex_structure":(("rights_obligations",.8),("presentation_classification",.6)), "end_of_period":(("cut_off",.7),),
 "revenue_period_end":(("cut_off",.9),("existence_occurrence",.6)), "high_monetary_value":(("valuation_accuracy",.7),),
 "unusual_amount":(("valuation_accuracy",.8),), "flow_analysis":(("existence_occurrence",.5),("valuation_accuracy",.6)),
 "benford_two_digit":(("valuation_accuracy",.6),), "empty_text_field":(("completeness",.6),),
 "reversal":(("cut_off",.6),("completeness",.5)), "personal_expense":(("existence_occurrence",.9),("presentation_classification",.7)),
 "payroll_anomaly":(("existence_occurrence",.8),("rights_obligations",.6)),
}

def ensure_tables(): Base.metadata.create_all(bind=engine)
def serialize(row): return {"id":row.id,"control_point_id":row.control_point_id,"name":row.control_point_name,"category":row.category,"status":row.status,"confidence":row.confidence,"explanation_text":row.explanation_text,"evidence":row.evidence or {},"created_at":row.created_at.isoformat()}
def evaluate(tx, context, db):
    db.query(ControlPointResult).filter(ControlPointResult.transaction_id==tx.id).delete(synchronize_session=False)
    rows=[]
    for control in DEFAULT_CONTROLS:
        r=control.evaluate(tx,context)
        rows.append(ControlPointResult(transaction_id=tx.id,control_point_id=r.control_point_id,control_point_name=r.name,category=r.category.value,status=r.status.value,confidence=r.confidence,explanation_text=r.explanation_text,evidence=r.evidence))
    db.add_all(rows); db.commit()
    return sorted(rows,key=lambda r:(RISK_ORDER[r.status],-r.confidence))

@router.post("/control-points/init")
def init_control_points(db:Session=Depends(get_db)):
    ensure_tables()
    if not db.query(ControlPointAssertionMap).first():
        db.add_all([ControlPointAssertionMap(control_point_id=cp,assertion=a,weight=w) for cp,mappings in DEFAULT_MAP.items() for a,w in mappings]); db.commit()
    return {"status":"ready","controls":len(DEFAULT_CONTROLS),"assertions":len(ASSERTIONS)}

@router.get("/transactions")
def list_transactions(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),sort_by_risk:bool=False,db:Session=Depends(get_db)):
    ensure_tables(); items=db.query(Transaction).order_by(Transaction.date.desc()).offset((page-1)*page_size).limit(page_size).all()
    payload=[]
    for tx in items:
        latest=db.query(ControlPointResult).filter_by(transaction_id=tx.id).all()
        risk=max((r.confidence for r in latest),default=0)
        payload.append({"id":tx.id,"txn_id":tx.txn_id,"date":tx.date.isoformat(),"vendor_name":tx.vendor_name,"amount":float(tx.amount or 0),"account_head":tx.account_head,"risk":risk,"failed_controls":sum(r.status!="pass" for r in latest)})
    if sort_by_risk: payload.sort(key=lambda x:-x["risk"])
    return {"items":payload,"page":page,"total":db.query(Transaction).count()}

@router.get("/transactions/{transaction_id}/control-points")
def transaction_control_points(transaction_id:int,refresh:bool=False,db:Session=Depends(get_db)):
    ensure_tables(); tx=db.get(Transaction,transaction_id)
    if not tx: raise HTTPException(404,"Transaction not found")
    context=db.query(Transaction).all(); existing=db.query(ControlPointResult).filter_by(transaction_id=tx.id).all()
    rows=evaluate(tx,context,db) if refresh or not existing else sorted(existing,key=lambda r:(RISK_ORDER[r.status],-r.confidence))
    return {"transaction_id":tx.id,"txn_id":tx.txn_id,"control_points":[serialize(r) for r in rows]}

@router.get("/claims/{claim_id}/control-points")
def claim_control_points(claim_id:str, refresh:bool=False, db:Session=Depends(get_db)):
    """Expose existing ML, Benford, and related-party outputs as claim controls."""
    ensure_tables(); claim=db.query(ExpenseClaim).filter_by(claim_id=claim_id).first()
    if not claim: raise HTTPException(404,"Claim not found")
    existing=db.query(ControlPointResult).filter_by(claim_id=claim_id).all()
    if refresh or not existing:
        db.query(ControlPointResult).filter_by(claim_id=claim_id).delete(synchronize_session=False)
        context=db.query(ExpenseClaim).all(); existing=[]
        for control in CLAIM_CONTROLS:
            r=control.evaluate(claim,context); existing.append(ControlPointResult(claim_id=claim_id,control_point_id=r.control_point_id,control_point_name=r.name,category=r.category.value,status=r.status.value,confidence=r.confidence,explanation_text=r.explanation_text,evidence=r.evidence))
        db.add_all(existing); db.commit()
    return {"claim_id":claim_id,"control_points":[serialize(r) for r in sorted(existing,key=lambda r:(RISK_ORDER[r.status],-r.confidence))]}

@router.post("/transactions/{transaction_id}/control-points/evaluate")
def evaluate_transaction(transaction_id:int,db:Session=Depends(get_db)):
    ensure_tables(); tx=db.get(Transaction,transaction_id)
    if not tx: raise HTTPException(404,"Transaction not found")
    return {"transaction_id":tx.id,"control_points":[serialize(r) for r in evaluate(tx,db.query(Transaction).all(),db)]}

@router.get("/accounts/{account}/assertion-risk")
def assertion_risk(account:str,db:Session=Depends(get_db)):
    ensure_tables(); txs=db.query(Transaction).filter(Transaction.account_head==account).all()
    if not txs: raise HTTPException(404,"Account not found")
    mapping=defaultdict(list)
    for m in db.query(ControlPointAssertionMap).all(): mapping[m.control_point_id].append((m.assertion,m.weight))
    totals=defaultdict(float); weights=defaultdict(float)
    for tx in txs:
        rows=db.query(ControlPointResult).filter_by(transaction_id=tx.id).all() or evaluate(tx,db.query(Transaction).all(),db)
        for row in rows:
            for assertion,weight in mapping.get(row.control_point_id,DEFAULT_MAP.get(row.control_point_id,())):
                risk=row.confidence if row.status!="pass" else 0; totals[assertion]+=risk*weight; weights[assertion]+=weight
    return {"account":account,"entry_count":len(txs),"assertion_risk":{a:round(totals[a]/weights[a],1) if weights[a] else 0 for a in ASSERTIONS}}

@router.get("/accounts/assertion-risk")
def all_assertion_risks(db:Session=Depends(get_db)):
    accounts=[a[0] for a in db.query(Transaction.account_head).filter(Transaction.account_head.isnot(None)).distinct().all()]
    return [assertion_risk(account,db) for account in accounts]

def _ratio_value(rows, definition, ratio_id):
    # Empty mappings are intentional for the universal cash-spend control.
    if ratio_id == "cash_to_expense":
        numerator=sum(float(x.amount or 0) for x in rows if (x.payment_method or "").lower()=="cash")
        denominator=sum(float(x.amount or 0) for x in rows)
    else:
        numerator=sum(float(x.amount or 0) for x in rows if x.account_head in definition["numerator_accounts"])
        denominator=sum(float(x.amount or 0) for x in rows if x.account_head in definition["denominator_accounts"])
    return numerator / denominator * 100 if denominator else 0

@router.get("/ratios/{ratio_id}/trend")
def ratio_trend(ratio_id:str,periods:int=Query(5,ge=2,le=24),db:Session=Depends(get_db)):
    if ratio_id not in RATIO_DEFINITIONS: raise HTTPException(404,"Unknown ratio")
    definition=RATIO_DEFINITIONS[ratio_id]; groups=defaultdict(list)
    for tx in db.query(Transaction).all(): groups[tx.date.strftime("%Y-%m")].append(tx)
    points=[]
    for period,rows in sorted(groups.items())[-periods:]: points.append({"period":period,"value":round(_ratio_value(rows,definition,ratio_id),2)})
    values=[p["value"] for p in points]; mean=sum(values)/len(values) if values else 0; std=(sum((x-mean)**2 for x in values)/len(values))**.5 if values else 0
    for p in points: p.update({"expected_low":round(max(0,mean-std),2),"expected_high":round(mean+std,2),"outside_expected_range":p["value"]<mean-std or p["value"]>mean+std})
    return {"ratio_id":ratio_id,"name":definition["name"],"points":points}

COLUMN_ALIASES={"transaction_id":"txn_id","voucher_no":"txn_id","transaction_date":"date","posting_date":"date","payee":"vendor_name","counterparty":"vendor_name","narration":"description","memo":"description","account":"account_head","account_name":"account_head","method":"payment_method","invoice_no":"invoice_number"}
@router.post("/ledger/upload")
async def upload_ledger(file:UploadFile=File(...),source_name:str="ledger",db:Session=Depends(get_db)):
    ensure_tables(); suffix=file.filename.rsplit(".",1)[-1].lower() if file.filename else ""
    if suffix not in {"csv","xlsx","xls"}: raise HTTPException(400,"Upload CSV or Excel ledger files.")
    raw=await file.read(); df=pd.read_csv(BytesIO(raw)) if suffix=="csv" else pd.read_excel(BytesIO(raw)); df.columns=[COLUMN_ALIASES.get(str(c).strip().lower().replace(" ","_"),str(c).strip().lower().replace(" ","_")) for c in df.columns]
    required={"date","amount","account_head","vendor_name"}; missing=required-set(df.columns)
    if missing: raise HTTPException(422,f"Missing required mapped columns: {sorted(missing)}")
    batch=IngestionBatch(source_name=source_name,original_filename=file.filename,column_mapping=COLUMN_ALIASES); db.add(batch); db.flush()
    # Keep an in-memory master set so repeated payees in a single upload do not
    # create duplicate pending Vendor rows before the final transaction commit.
    known_vendors={name for (name,) in db.query(Vendor.vendor_name).all()}
    accepted=0; errors=[]
    for index,row in df.drop_duplicates().iterrows():
        try:
            amount=float(str(row["amount"]).replace(",","").replace("₹","").replace("$","")); date=pd.to_datetime(row["date"]).date()
            if amount<=0 or not str(row["vendor_name"]).strip() or not str(row["account_head"]).strip(): raise ValueError("amount, payee, and account are required")
            vendor=str(row["vendor_name"]).strip(); txn_id=str(row.get("txn_id") or f"{batch.id}-{index+1}")
            if db.query(Transaction).filter_by(txn_id=txn_id).first(): raise ValueError("duplicate transaction ID")
            if vendor not in known_vendors:
                db.add(Vendor(vendor_name=vendor,status="Unapproved")); known_vendors.add(vendor)
            db.add(Transaction(txn_id=txn_id,date=date,vendor_name=vendor,amount=amount,account_head=str(row["account_head"]).strip(),description=str(row.get("description") or ""),entry_method=str(row.get("entry_method") or "system"),source_system=source_name,invoice_number=str(row.get("invoice_number") or "") or None,ingestion_batch_id=batch.id)); accepted+=1
        except Exception as exc: errors.append({"row":int(index)+2,"error":str(exc)})
    batch.accepted_rows=accepted; batch.rejected_rows=len(errors); db.commit()
    return {"batch_id":batch.id,"accepted_rows":accepted,"rejected_rows":len(errors),"errors":errors[:100]}
