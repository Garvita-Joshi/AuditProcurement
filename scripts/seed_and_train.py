"""
AuditAI — One-command setup: seed data, initialize DB, train models, score claims.

Usage:
    python scripts/seed_and_train.py

Prerequisites:
    - PostgreSQL running
    - Backend API running: python -m uvicorn backend.app.main:app --reload
"""
import os
import subprocess
import sys
import time

import requests

API_URL = "http://127.0.0.1:8000/api/v1"


def main():
    print("=== AuditAI: Seed & Train Pipeline ===")

    # Step 1: Generate synthetic data
    print("\n[1/6] Generating synthetic expense claims...")
    subprocess.run([sys.executable, "scripts/generate_expense_claims.py"], check=True)

    # Step 2: Initialize database
    print("\n[2/6] Initializing database...")
    try:
        r = requests.post(f"{API_URL}/claims/init-db")
        r.raise_for_status()
        print(f"  DB init: {r.json().get('message')}")
    except requests.exceptions.RequestException as e:
        print(f"  Error connecting to API. Is it running? {e}")
        print("  Please start the backend with: uvicorn backend.app.main:app --reload")
        return

    # Step 3: Upload claims
    print("\n[3/6] Uploading expense claims...")
    with open("data/expense_claims.csv", "rb") as f:
        r = requests.post(f"{API_URL}/claims/upload", files={"file": ("expense_claims.csv", f, "text/csv")})
    
    if r.status_code in (200, 201):
        print(f"  Upload result: {r.json().get('message')}")
    else:
        print(f"  Upload failed: {r.text}")
        return

    # Step 4: Train models
    print("\n[4/6] Training ML pipeline (Autoencoder + Isolation Forest)...")
    r = requests.post(f"{API_URL}/fraud/train")
    if r.status_code == 200:
        print(f"  Training result: {r.json().get('message')}")
    else:
        print(f"  Training failed: {r.text}")
        return

    # Step 5: Score all claims
    print("\n[5/6] Scoring all claims...")
    r = requests.post(f"{API_URL}/fraud/score")
    if r.status_code == 200:
        data = r.json()
        print(f"  Scored {data.get('scored_count')} claims. {data.get('flagged_count')} flagged as anomalies.")
    else:
        print(f"  Scoring failed: {r.text}")

    # Step 6: Generate audit reports for flagged claims
    print("\n[6/6] Generating audit reports for flagged claims...")
    r = requests.post(f"{API_URL}/reports/generate-all")
    if r.status_code == 200:
        print(f"  Generated {r.json().get('generated_count')} reports.")
    else:
        print(f"  Report generation failed: {r.text}")

    print("\n=== Pipeline complete! ===")
    print("Dashboard: http://localhost:5173")
    print("API docs:  http://localhost:8000/docs")


if __name__ == "__main__":
    main()
