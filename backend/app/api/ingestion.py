import io
import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import Dict, Any

from backend.app.db import get_db, Base, engine
from backend.app.models.transaction import Vendor, Transaction
from backend.app.core.pipeline import clean_transaction_data, clean_vendor_data

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])

@router.post("/init-db", status_code=status.HTTP_200_OK)
def init_db():
    """
    Creates all database tables in PostgreSQL.
    """
    try:
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database tables created successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize database: {str(e)}"
        )

@router.post("/vendors", status_code=status.HTTP_201_CREATED)
async def ingest_vendors(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Uploads and processes the Vendor Master CSV.
    Uses bulk upsert on vendor_name to handle duplicates.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV."
        )
        
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        cleaned_df, errors = clean_vendor_data(df)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error reading CSV: {str(e)}"
        )

    # Insert or Update (upsert) in DB
    success_count = 0
    for _, row in cleaned_df.iterrows():
        # Prep upsert query
        stmt = insert(Vendor).values(
            vendor_name=row["vendor_name"],
            gstin=row["gstin"],
            address=row["address"],
            phone_number=row["phone_number"],
            bank_account=row["bank_account"],
            status=row["status"],
            registration_date=row["registration_date"]
        )
        
        # On conflict update everything except name
        update_dict = {c.name: c for c in stmt.excluded if c.name != 'vendor_name'}
        stmt = stmt.on_conflict_do_update(
            index_elements=['vendor_name'],
            set_=update_dict
        )
        
        db.execute(stmt)
        success_count += 1
        
    db.commit()
    
    return {
        "status": "success",
        "processed_rows": len(df),
        "loaded_vendors": success_count,
        "failed_rows": len(errors),
        "errors": errors
    }

@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def ingest_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Uploads and processes the Transactions CSV.
    Cleans messy currency formats, parses dates, and creates auto-placeholder vendors.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV."
        )
        
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        cleaned_df, errors = clean_transaction_data(df)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error reading or parsing CSV: {str(e)}"
        )

    loaded_count = 0
    db_errors = []
    
    for idx, row in cleaned_df.iterrows():
        vendor_name = row["vendor_name"]
        
        # Verify if vendor exists in DB, otherwise auto-create as 'Unapproved'
        vendor = db.query(Vendor).filter(Vendor.vendor_name == vendor_name).first()
        if not vendor:
            # Auto-create placeholder vendor to satisfy foreign key constraint
            placeholder = Vendor(
                vendor_name=vendor_name,
                status="Unapproved",  # Unapproved by default since it wasn't pre-registered
                gstin=None,
                address=None,
                phone_number=None,
                bank_account=None,
                registration_date=None
            )
            db.add(placeholder)
            db.commit()
            
        # Create transaction model
        transaction = Transaction(
            txn_id=row["txn_id"],
            date=row["date"],
            time=row["time"],
            vendor_name=vendor_name,
            amount=row["amount"],
            payment_method=row["payment_method"],
            created_by=row["created_by"],
            approved_by=row["approved_by"],
            account_head=row["account_head"],
            is_fraud=row["is_fraud"],
            fraud_type=row["fraud_type"]
        )
        
        try:
            # Check for existing txn_id to avoid unique constraint error
            existing = db.query(Transaction).filter(Transaction.txn_id == transaction.txn_id).first()
            if existing:
                db_errors.append({
                    "row_number": idx + 1,
                    "txn_id": transaction.txn_id,
                    "errors": [f"Transaction ID {transaction.txn_id} already exists in database."]
                })
                continue
                
            db.add(transaction)
            loaded_count += 1
        except Exception as e:
            db.rollback()
            db_errors.append({
                "row_number": idx + 1,
                "txn_id": transaction.txn_id,
                "errors": [f"Database error: {str(e)}"]
            })
            
    db.commit()
    
    return {
        "status": "success" if not db_errors and not errors else "partial_success",
        "processed_rows": len(df),
        "loaded_transactions": loaded_count,
        "parsing_errors_count": len(errors),
        "db_errors_count": len(db_errors),
        "parsing_errors": errors,
        "db_errors": db_errors
    }

@router.get("/stats", status_code=status.HTTP_200_OK)
def get_stats(db: Session = Depends(get_db)):
    """
    Returns summary statistics of loaded data to confirm ingestion success.
    """
    try:
        vendor_count = db.query(Vendor).count()
        transaction_count = db.query(Transaction).count()
        fraud_count = db.query(Transaction).filter(Transaction.is_fraud == True).count()
        
        # Calculate total amount (casting Numeric to float for JSON response compatibility)
        total_amt_query = db.query(Transaction.amount).all()
        total_amount = float(sum(t[0] for t in total_amt_query if t[0] is not None))
        
        return {
            "status": "success",
            "vendors_in_db": vendor_count,
            "transactions_in_db": transaction_count,
            "fraud_transactions_in_db": fraud_count,
            "total_transaction_amount": total_amount
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch database statistics: {str(e)}"
        )
