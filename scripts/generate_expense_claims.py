"""
AuditAI — Synthetic Expense Claims Generator

Generates ~2000 expense claims with embedded fraud patterns.
Normal claims (~1850) + Fraudulent claims (~150)
Outputs to data/expense_claims.csv and data/receipts/ (images).
"""
import csv
import logging
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# Set seeds for reproducibility
random.seed(42)
np.random.seed(42)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

fake = Faker("en_IN")
fake.seed_instance(42)

# Configuration
NUM_CLAIMS = 2000
FRAUD_RATE = 0.075
NUM_FRAUD = int(NUM_CLAIMS * FRAUD_RATE)
NUM_NORMAL = NUM_CLAIMS - NUM_FRAUD

OUTPUT_DIR = Path("data")
RECEIPT_DIR = OUTPUT_DIR / "receipts"

# Data pools
EMPLOYEES = [f"EMP{i:03d}" for i in range(1, 51)]
EMPLOYEE_NAMES = {emp: fake.name() for emp in EMPLOYEES}

CATEGORIES = ["Meals", "Travel", "Office Supplies", "Client Entertainment", "Transport", "Accommodation"]

VENDORS = [
    "Starbucks Coffee", "Amazon India", "Uber Rides", "Ola Cabs", "Zomato", "Swiggy",
    "MakeMyTrip", "IndiGo Airlines", "Vistara Airlines", "Taj Hotels", "ITC Hotels",
    "Domino's Pizza", "McDonald's", "KFC", "Subway", "Croma", "Reliance Digital",
    "Flipkart", "BigBasket", "Blinkit", "Zepto", "Oyo Rooms", "IRCTC", "Air India",
    "ClearTrip", "Yatra", "BookMyShow", "Shoppers Stop", "Lifestyle", "Decathlon",
    "WeWork", "Regus", "AWFIS", "Stationery Hub", "Local Taxi", "Cafe Coffee Day"
]

FRAUD_VENDORS_MAP = {
    "Starbucks Coffee": "Starbuks Coffee",
    "Amazon India": "Amazn Inc",
    "Uber Rides": "Uberr Rides",
    "Flipkart": "Flipkrt Online",
    "Zomato": "Zomto Food",
    "Swiggy": "Swiggi Delivery",
    "Ola Cabs": "Olaa Cabs",
    "MakeMyTrip": "Make My Trp",
    "Domino's Pizza": "Domions Pizza",
    "McDonald's": "McDonaIds",  # Capital I instead of l
}

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RECEIPT_DIR.mkdir(parents=True, exist_ok=True)


def _generate_normal_claim(claim_id_idx: int) -> dict:
    """Generate a single normal claim."""
    emp_id = random.choice(EMPLOYEES)
    # Log-normal amount (mean ~2000 INR, tail to 50000)
    mu, sigma = 7.6, 1.0  # e^7.6 ~= 2000
    amount = min(50000, max(200, round(np.random.lognormal(mu, sigma), 2)))
    
    # Random date in 2025-2026 financial year
    start_date = date(2025, 4, 1)
    end_date = date(2026, 3, 31)
    days_between = (end_date - start_date).days
    
    # Try to pick a weekday
    for _ in range(10):
        claim_date = start_date + timedelta(days=random.randint(0, days_between))
        if claim_date.weekday() < 5:  # 0-4 are Mon-Fri
            break
            
    category = random.choice(CATEGORIES)
    
    # OCR amount occasionally missing, usually matching
    ocr_amount = amount if random.random() > 0.1 else None

    return {
        "claim_id": f"CLM-{claim_id_idx:05d}",
        "employee_id": emp_id,
        "employee_name": EMPLOYEE_NAMES[emp_id],
        "claimed_amount": amount,
        "vendor_name": random.choice(VENDORS),
        "claimed_date": claim_date.isoformat(),
        "category": category,
        "description": f"{category} expense",
        "is_fraud": False,
        "fraud_type": "none",
        "ocr_amount": ocr_amount,
    }


def generate_claims():
    """Generate the full dataset."""
    logger.info("Generating %d normal claims...", NUM_NORMAL)
    claims = []
    claim_idx = 1
    
    for _ in range(NUM_NORMAL):
        claims.append(_generate_normal_claim(claim_idx))
        claim_idx += 1
        
    logger.info("Injecting %d fraudulent claims...", NUM_FRAUD)
    
    fraud_types = ["amount_inflation", "duplicate", "fake_vendor", "split_transaction", "weekend_claim"]
    counts = {ft: NUM_FRAUD // len(fraud_types) for ft in fraud_types}
    # Add remainder to first type
    counts["amount_inflation"] += NUM_FRAUD % len(fraud_types)
    
    # 1. Amount Inflation
    for _ in range(counts["amount_inflation"]):
        claim = _generate_normal_claim(claim_idx)
        # Real receipt is 20-80% lower than claimed amount
        real_amount = round(claim["claimed_amount"] * random.uniform(0.2, 0.8), 2)
        claim["ocr_amount"] = real_amount
        claim["is_fraud"] = True
        claim["fraud_type"] = "amount_inflation"
        claims.append(claim)
        claim_idx += 1
        
    # 2. Duplicates
    for _ in range(counts["duplicate"]):
        # Pick a random existing claim to duplicate
        base_claim = random.choice(claims[:NUM_NORMAL])
        dup_claim = base_claim.copy()
        dup_claim["claim_id"] = f"CLM-{claim_idx:05d}"
        # Small tweak to amount (+- 2%)
        dup_claim["claimed_amount"] = round(dup_claim["claimed_amount"] * random.uniform(0.98, 1.02), 2)
        dup_claim["ocr_amount"] = dup_claim["claimed_amount"]
        # Date within 7 days
        base_date = date.fromisoformat(base_claim["claimed_date"])
        dup_claim["claimed_date"] = (base_date + timedelta(days=random.randint(1, 5))).isoformat()
        
        dup_claim["is_fraud"] = True
        dup_claim["fraud_type"] = "duplicate"
        claims.append(dup_claim)
        claim_idx += 1
        
    # 3. Fake Vendors (Typosquatting)
    for _ in range(counts["fake_vendor"]):
        claim = _generate_normal_claim(claim_idx)
        # Replace with fake vendor
        real_vendor = random.choice(list(FRAUD_VENDORS_MAP.keys()))
        fake_vendor = FRAUD_VENDORS_MAP[real_vendor]
        claim["vendor_name"] = fake_vendor
        claim["is_fraud"] = True
        claim["fraud_type"] = "fake_vendor"
        claims.append(claim)
        claim_idx += 1
        
    # 4. Split Transactions (Same day, same employee, large amount split)
    split_group_count = counts["split_transaction"] // 2
    for _ in range(split_group_count):
        emp_id = random.choice(EMPLOYEES)
        claim_date = date(2025, 4, 1) + timedelta(days=random.randint(0, 360))
        
        # Claim 1
        c1 = {
            "claim_id": f"CLM-{claim_idx:05d}",
            "employee_id": emp_id,
            "employee_name": EMPLOYEE_NAMES[emp_id],
            "claimed_amount": round(random.uniform(4000, 4900), 2),
            "vendor_name": random.choice(VENDORS),
            "claimed_date": claim_date.isoformat(),
            "category": "Office Supplies",
            "description": "Equipment part 1",
            "is_fraud": True,
            "fraud_type": "split_transaction",
            "ocr_amount": None,
        }
        claims.append(c1)
        claim_idx += 1
        
        # Claim 2
        c2 = {
            "claim_id": f"CLM-{claim_idx:05d}",
            "employee_id": emp_id,
            "employee_name": EMPLOYEE_NAMES[emp_id],
            "claimed_amount": round(random.uniform(4000, 4900), 2),
            "vendor_name": c1["vendor_name"],
            "claimed_date": claim_date.isoformat(),
            "category": "Office Supplies",
            "description": "Equipment part 2",
            "is_fraud": True,
            "fraud_type": "split_transaction",
            "ocr_amount": None,
        }
        claims.append(c2)
        claim_idx += 1

    # 5. Weekend Claims
    for _ in range(counts["weekend_claim"]):
        claim = _generate_normal_claim(claim_idx)
        # Force to weekend
        base_date = date.fromisoformat(claim["claimed_date"])
        days_to_saturday = 5 - base_date.weekday()
        if days_to_saturday <= 0:
            days_to_saturday += 7
        weekend_date = base_date + timedelta(days=days_to_saturday)
        
        claim["claimed_date"] = weekend_date.isoformat()
        claim["is_fraud"] = True
        claim["fraud_type"] = "weekend_claim"
        claims.append(claim)
        claim_idx += 1

    # Shuffle claims
    random.shuffle(claims)
    
    # Write to CSV
    csv_file = OUTPUT_DIR / "expense_claims.csv"
    with open(csv_file, "w", newline="") as f:
        fieldnames = list(claims[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(claims)
        
    logger.info("Saved %d claims to %s", len(claims), csv_file)
    
    # Generate some synthetic receipts
    logger.info("Generating synthetic receipt images...")
    sample_claims = random.sample(claims, 50)
    for c in sample_claims:
        _generate_receipt_image(c)
        
    # Print summary
    print(f"\n=== Expense Claims Generator ===")
    print(f"Total claims: {len(claims)}")
    print(f"Normal: {NUM_NORMAL} ({100-FRAUD_RATE*100}%)")
    print(f"Fraudulent: {NUM_FRAUD} ({FRAUD_RATE*100}%)")
    for ft, count in counts.items():
        print(f"  - {ft}: {count}")
    print(f"Receipt images generated: 50")
    print(f"Output: {csv_file}")


def _generate_receipt_image(claim: dict):
    """Draw a simple synthetic receipt using Pillow."""
    width, height = 600, 800
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    
    # For a real implementation we would load a true type font
    # Here we just use the default font, but we'll try to load a basic one if possible
    font = None
    try:
        # Try to load a system font if available, fallback to default
        import platform
        if platform.system() == "Darwin":
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        else:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        
    vendor = claim["vendor_name"].upper()
    amt = claim["ocr_amount"] or claim["claimed_amount"]
    d_str = claim["claimed_date"]
    
    # Draw receipt header
    draw.text((width/2 - 100, 50), vendor, fill="black", font=font)
    draw.text((width/2 - 60, 100), f"Date: {d_str}", fill="black", font=small_font)
    draw.text((width/2 - 80, 140), "TAX ID: 27AABCU9603R1Z2", fill="black", font=small_font)
    
    draw.line([(50, 180), (width-50, 180)], fill="black", width=2)
    
    # Line items
    y = 220
    for i in range(random.randint(2, 5)):
        item_amt = round(amt / 4, 2)
        draw.text((60, y), f"Item {i+1}", fill="black", font=small_font)
        draw.text((width-150, y), f"${item_amt:.2f}", fill="black", font=small_font)
        y += 40
        
    draw.line([(50, y+20), (width-50, y+20)], fill="black", width=2)
    
    # Total
    draw.text((60, y+60), "TOTAL", fill="black", font=font)
    draw.text((width-180, y+60), f"${amt:.2f}", fill="black", font=font)
    
    img_path = RECEIPT_DIR / f"receipt_{claim['claim_id']}.png"
    img.save(img_path)


if __name__ == "__main__":
    generate_claims()
