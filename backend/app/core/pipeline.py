import pandas as pd
import numpy as np
import re
from datetime import datetime, date, time
from typing import Tuple, List, Dict, Any, Optional

def clean_currency_string(val: Any) -> float:
    """
    Cleans a currency string (e.g., '₹ 1,50,000.00', '$ 500') and converts it to float.
    """
    if pd.isna(val) or val == "" or str(val).strip() == "":
        return 0.0
    
    # Cast to string and strip spaces
    val_str = str(val).strip()
    
    # Remove currency symbols (₹, $, £, €, etc.), commas, and extra spaces
    cleaned = re.sub(r'[₹$£€,\s]', '', val_str)
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def parse_mixed_date(val: Any) -> date:
    """
    Parses date strings with mixed formats:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - MM-DD-YYYY
    Returns a datetime.date object.
    """
    if pd.isna(val) or val == "" or str(val).strip() == "":
        raise ValueError("Empty date string")
        
    date_str = str(val).strip()
    
    # Common date format patterns to attempt
    formats = [
        "%Y-%m-%d",    # 2025-04-12
        "%d/%m/%Y",    # 12/04/2025
        "%m-%d-%Y",    # 04-12-2025
        "%Y/%m/%d",    # 2025/04/12
        "%d-%m-%Y",    # 12-04-2025
        "%d-%b-%Y",    # 12-Apr-2025
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
            
    # If none matches, try parsing using pandas utility
    try:
        return pd.to_datetime(date_str).date()
    except Exception as e:
        raise ValueError(f"Could not parse date: {date_str}") from e

def parse_time_string(val: Any) -> Optional[time]:
    """
    Parses time strings to datetime.time.
    """
    if pd.isna(val) or val == "" or str(val).strip() == "":
        return None
        
    time_str = str(val).strip()
    
    formats = [
        "%H:%M:%S",  # 14:30:15
        "%H:%M",     # 14:30
        "%I:%M:%S %p", # 02:30:15 PM
        "%I:%M %p"   # 02:30 PM
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
            
    # Try custom parsing if it has no seconds or has peculiar format
    try:
        parts = time_str.split(":")
        if len(parts) >= 2:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return time(h, m, s)
    except Exception:
        pass
        
    return None

def sanitize_raw_data(row: pd.Series) -> Dict[str, Any]:
    raw_dict = row.to_dict()
    sanitized = {}
    for k, v in raw_dict.items():
        if pd.isna(v):
            sanitized[k] = None
        else:
            sanitized[k] = v
    return sanitized

def clean_transaction_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Cleans the transactions DataFrame.
    Returns:
        - A cleaned DataFrame ready to be inserted.
        - A list of error dictionaries containing details of rejected rows.
    """
    cleaned_rows = []
    errors = []
    
    # Standardize column names (strip whitespace and lowercase)
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Check if necessary columns exist
    required_cols = ["txn_id", "date", "vendor_name", "amount"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in CSV: {missing_cols}")
        
    for idx, (index, row) in enumerate(df.iterrows()):
        row_num = idx + 1
        row_errors = []
        
        # 1. Clean txn_id (required, non-empty)
        raw_txn_id = row.get("txn_id")
        if pd.isna(raw_txn_id) or str(raw_txn_id).strip() == "":
            row_errors.append("Missing transaction ID (txn_id)")
            txn_id = None
        else:
            txn_id = str(raw_txn_id).strip()
            
        # 2. Clean date (required)
        raw_date = row.get("date")
        txn_date = None
        if pd.isna(raw_date) or str(raw_date).strip() == "":
            row_errors.append("Missing date")
        else:
            try:
                txn_date = parse_mixed_date(raw_date)
            except Exception as e:
                row_errors.append(str(e))
                
        # 3. Clean amount (required)
        raw_amount = row.get("amount")
        amount = 0.0
        try:
            amount = clean_currency_string(raw_amount)
            if amount <= 0:
                row_errors.append(f"Invalid transaction amount: {raw_amount}")
        except Exception as e:
            row_errors.append(f"Error parsing amount {raw_amount}: {str(e)}")
            
        # 4. Clean vendor_name (required, non-empty)
        raw_vendor = row.get("vendor_name")
        if pd.isna(raw_vendor) or str(raw_vendor).strip() == "":
            row_errors.append("Missing vendor name")
            vendor_name = None
        else:
            vendor_name = str(raw_vendor).strip()
            
        # If there are critical errors, reject this row
        if row_errors:
            errors.append({
                "row_number": row_num,
                "txn_id": txn_id or "UNKNOWN",
                "errors": row_errors,
                "raw_data": sanitize_raw_data(row)
            })
            continue
            
        # 5. Clean optional fields
        # Time
        raw_time = row.get("time")
        txn_time = parse_time_string(raw_time) if pd.notna(raw_time) else None
        
        # Payment method (trim and default to UNKNOWN if blank)
        raw_pm = row.get("payment_method")
        payment_method = str(raw_pm).strip() if pd.notna(raw_pm) and str(raw_pm).strip() != "" else "UNKNOWN"
        
        # Created by / Approved by (trim, default to UNKNOWN)
        raw_cb = row.get("created_by")
        created_by = str(raw_cb).strip() if pd.notna(raw_cb) and str(raw_cb).strip() != "" else "UNKNOWN"
        
        raw_ab = row.get("approved_by")
        approved_by = str(raw_ab).strip() if pd.notna(raw_ab) and str(raw_ab).strip() != "" else "UNKNOWN"
        
        # Account head
        raw_ah = row.get("account_head")
        account_head = str(raw_ah).strip() if pd.notna(raw_ah) and str(raw_ah).strip() != "" else "UNKNOWN"
        
        # Ground truth flag (if present, default False)
        raw_if = row.get("is_fraud")
        is_fraud = False
        if pd.notna(raw_if):
            val_str = str(raw_if).strip().lower()
            is_fraud = val_str in ["true", "1", "yes", "t", "y"]
            
        raw_ft = row.get("fraud_type")
        fraud_type = str(raw_ft).strip() if pd.notna(raw_ft) and str(raw_ft).strip() != "" else "none"
        
        cleaned_rows.append({
            "txn_id": txn_id,
            "date": txn_date,
            "time": txn_time,
            "vendor_name": vendor_name,
            "amount": amount,
            "payment_method": payment_method,
            "created_by": created_by,
            "approved_by": approved_by,
            "account_head": account_head,
            "is_fraud": is_fraud,
            "fraud_type": fraud_type
        })
        
    cleaned_df = pd.DataFrame(cleaned_rows)
    return cleaned_df, errors

def clean_vendor_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Cleans the vendors DataFrame.
    """
    cleaned_rows = []
    errors = []
    
    df.columns = [col.strip().lower() for col in df.columns]
    
    required_cols = ["vendor_name"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in vendor CSV: {missing_cols}")
        
    for idx, (index, row) in enumerate(df.iterrows()):
        row_num = idx + 1
        row_errors = []
        
        raw_name = row.get("vendor_name")
        if pd.isna(raw_name) or str(raw_name).strip() == "":
            row_errors.append("Missing vendor name")
            vendor_name = None
        else:
            vendor_name = str(raw_name).strip()
            
        if row_errors:
            errors.append({
                "row_number": row_num,
                "errors": row_errors,
                "raw_data": sanitize_raw_data(row)
            })
            continue
            
        # Clean optional metadata
        gstin = str(row.get("gstin")).strip() if pd.notna(row.get("gstin")) and str(row.get("gstin")).strip() != "" else None
        address = str(row.get("address")).strip() if pd.notna(row.get("address")) and str(row.get("address")).strip() != "" else None
        phone_number = str(row.get("phone_number")).strip() if pd.notna(row.get("phone_number")) and str(row.get("phone_number")).strip() != "" else None
        bank_account = str(row.get("bank_account")).strip() if pd.notna(row.get("bank_account")) and str(row.get("bank_account")).strip() != "" else None
        
        raw_status = row.get("status")
        status = str(raw_status).strip() if pd.notna(raw_status) and str(raw_status).strip() != "" else "Approved"
        # Standardize status
        if status.lower() in ["approved", "active", "y", "yes"]:
            status = "Approved"
        else:
            status = "Unapproved"
            
        raw_reg = row.get("registration_date")
        reg_date = None
        if pd.notna(raw_reg) and str(raw_reg).strip() != "":
            try:
                reg_date = parse_mixed_date(raw_reg)
            except Exception:
                pass # Non-critical if registration date parse fails, leave as null
                
        cleaned_rows.append({
            "vendor_name": vendor_name,
            "gstin": gstin,
            "address": address,
            "phone_number": phone_number,
            "bank_account": bank_account,
            "status": status,
            "registration_date": reg_date
        })
        
    cleaned_df = pd.DataFrame(cleaned_rows)
    return cleaned_df, errors
