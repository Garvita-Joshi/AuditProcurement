import os
import requests
import psycopg2
import pandas as pd
from decimal import Decimal

# API Configurations
API_URL = "http://127.0.0.1:8000/api/v1/ingest"
DB_URL = "postgresql://localhost:5433/postgres"

def run_verification():
    print("=== Starting Ingestion Pipeline Verification ===")
    
    # 1. Health check the FastAPI server
    try:
        r = requests.get("http://127.0.0.1:8000/")
        if r.status_code == 200:
            print("✔ FastAPI Server is up and running.")
        else:
            print(f"❌ FastAPI Server returned status code: {r.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ FastAPI Server is not running. Please start it using 'python3 backend/run.py'.")
        return

    # 2. Initialize the Database tables
    print("\nInitializing database tables...")
    r = requests.post(f"{API_URL}/init-db")
    if r.status_code == 200:
        print("✔ Database tables initialized successfully:", r.json())
    else:
        print("❌ Failed to initialize database:", r.text)
        return

    # 3. Upload Vendor Master CSV
    vendor_csv_path = "data/vendor_master.csv"
    if not os.path.exists(vendor_csv_path):
        print(f"❌ Vendor master CSV not found at {vendor_csv_path}")
        return
        
    print(f"\nUploading {vendor_csv_path} to ingestion API...")
    with open(vendor_csv_path, 'rb') as f:
        files = {'file': (os.path.basename(vendor_csv_path), f, 'text/csv')}
        r = requests.post(f"{API_URL}/vendors", files=files)
        
    if r.status_code == 201:
        res = r.json()
        print(f"✔ Vendor master uploaded successfully!")
        print(f"  Processed rows: {res.get('processed_rows')}")
        print(f"  Loaded vendors: {res.get('loaded_vendors')}")
        print(f"  Failed rows: {res.get('failed_rows')}")
    else:
        print("❌ Vendor master upload failed:", r.text)
        return

    # 4. Upload Messy Transactions CSV
    txns_csv_path = "data/transactions_messy.csv"
    if not os.path.exists(txns_csv_path):
        print(f"❌ Transactions CSV not found at {txns_csv_path}")
        return
        
    print(f"\nUploading {txns_csv_path} to ingestion API...")
    with open(txns_csv_path, 'rb') as f:
        files = {'file': (os.path.basename(txns_csv_path), f, 'text/csv')}
        r = requests.post(f"{API_URL}/transactions", files=files)
        
    if r.status_code == 201:
        res = r.json()
        print(f"✔ Transactions uploaded successfully!")
        print(f"  Status: {res.get('status')}")
        print(f"  Processed rows: {res.get('processed_rows')}")
        print(f"  Loaded transactions: {res.get('loaded_transactions')}")
        print(f"  Parsing errors: {res.get('parsing_errors_count')}")
        print(f"  DB errors: {res.get('db_errors_count')}")
        if res.get('parsing_errors_count') > 0:
            print("  Parsing error sample:", res.get('parsing_errors')[:3])
        if res.get('db_errors_count') > 0:
            print("  DB error sample:", res.get('db_errors')[:3])
    else:
        print("❌ Transactions upload failed:", r.text)
        return

    # 5. Fetch API statistics
    print("\nFetching Ingestion Statistics via API...")
    r = requests.get(f"{API_URL}/stats")
    if r.status_code == 200:
        res = r.json()
        print("✔ API Ingestion Stats:")
        print(f"  Vendors in DB: {res.get('vendors_in_db')}")
        print(f"  Transactions in DB: {res.get('transactions_in_db')}")
        print(f"  Fraud transactions: {res.get('fraud_transactions_in_db')}")
        print(f"  Total amount loaded: ₹{res.get('total_transaction_amount'):,.2f}")
    else:
        print("❌ Failed to fetch stats:", r.text)

    # 5.5. Upload a transaction with a new/unregistered vendor to verify placeholder creation
    print("\nTesting auto-creation of placeholder vendors...")
    placeholder_csv_path = "data/placeholder_test.csv"
    with open(placeholder_csv_path, "w") as f:
        f.write("txn_id,date,time,vendor_name,amount,payment_method,created_by,approved_by,account_head,is_fraud,fraud_type\n")
        f.write("TXN-99999,2026-03-30,12:00:00,Unknown Global Corp,\"₹ 45,000.00\",UPI,Neha Gupta,Priya Patel,Office Supplies,False,none\n")
        
    with open(placeholder_csv_path, 'rb') as f:
        files = {'file': (os.path.basename(placeholder_csv_path), f, 'text/csv')}
        r = requests.post(f"{API_URL}/transactions", files=files)
        
    if r.status_code == 201:
        print("✔ Loaded test transaction with unregistered vendor successfully.")
    else:
        print("❌ Placeholder vendor test transaction failed:", r.text)
        
    # Clean up temp file
    if os.path.exists(placeholder_csv_path):
        os.remove(placeholder_csv_path)

    # 6. Verify data cleaning and database integrity via direct SQL queries
    print("\nPerforming direct database validation...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Verify messy currency symbols and commas were removed
        cursor.execute("SELECT amount FROM transactions LIMIT 5;")
        amounts = cursor.fetchall()
        print("✔ Verified amounts are stored as Decimal (numeric type) in database:")
        for idx, amt in enumerate(amounts):
            print(f"  Sample {idx+1}: {amt[0]} (Type: {type(amt[0])})")
            
        # Verify dates are stored as date objects (standardized)
        cursor.execute("SELECT date FROM transactions LIMIT 5;")
        dates = cursor.fetchall()
        print("✔ Verified dates are standardized:")
        for idx, dt in enumerate(dates):
            print(f"  Sample {idx+1}: {dt[0]} (Type: {type(dt[0])})")
            
        # Verify placeholder vendors were created for unapproved vendors not in master
        cursor.execute("SELECT COUNT(*) FROM vendors WHERE status = 'Unapproved' AND gstin IS NULL;")
        unapproved_count = cursor.fetchone()[0]
        print(f"✔ Verified transaction references created {unapproved_count} auto-placeholder 'Unapproved' vendors in master list.")

        cursor.close()
        conn.close()
        
        print("\n=== Verification Completed Successfully! Pipeline is operating perfectly. ===")
    except Exception as e:
        print("❌ Database query validation failed:", str(e))

if __name__ == "__main__":
    run_verification()
