import os
import random
import datetime
import numpy as np
import pandas as pd
from faker import Faker

# Set seeds for reproducibility
random.seed(42)
np.random.seed(42)
fake = Faker('en_IN')  # Use Indian locale for realistic names/addresses if available

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# ----------------------------------------------------
# 1. Master Lists Definition
# ----------------------------------------------------

APPROVED_VENDORS = [
    "Reliance Industries Ltd", "Tata Consultancy Services Ltd", "Infosys Technologies",
    "HDFC Bank Ltd", "ICICI Bank Ltd", "Bharti Airtel Ltd", "Larsen & Toubro Ltd",
    "ITC Limited", "Wipro Limited", "Tech Mahindra Ltd", "Kotak Mahindra Bank",
    "Adani Enterprises", "Axis Bank Ltd", "Maruti Suzuki India", "Sun Pharmaceutical Industries",
    "State Bank of India", "Tata Steel Ltd", "Hindalco Industries Ltd", "Bajaj Auto Ltd",
    "Titan Company Ltd", "HCL Technologies Ltd", "NTPC Limited", "Power Grid Corporation of India",
    "Oil & Natural Gas Corporation", "Coal India Ltd", "J2 Office Supplies", "Apex Travel Solutions",
    "Blue Star Catering & Events", "Prime Marketing Agency", "Vivid Communications",
    "Metro Tech Solutions", "Delight Hospitality Group", "Elite Consulting Services",
    "National Power & Utilities", "Summit Property Rentals", "Safexpress Logistics",
    "Fast Track Courier Services", "Global Insurance Corp", "Digital Cloud Services",
    "Super Print Solutions", "Alpha Security Force", "General Hardware & Tools",
    "Matrix Facility Management", "Modern Stationers", "Nexus Legal Advisors",
    "Krishna Trading Co.", "K Trading Solutions"  # These two are approved, but part of shell network
]

UNAPPROVED_VENDORS = [
    "Sharma Enterprises", "Fake Invoice Corp", "KTC Enterprises", 
    "Singhania & Sons", "Gupta Logistics"
]

ALL_VENDORS = APPROVED_VENDORS + UNAPPROVED_VENDORS

ACCOUNT_HEADS = [
    "Office Supplies", "Travel & Entertainment", "Consulting Fees", "Marketing",
    "IT Infrastructure", "Utilities", "Salaries", "Rent", "Logistics & Courier",
    "Catering & Hospitality", "Legal & Professional Fees", "Security Services",
    "Maintenance & Repairs", "Insurance"
]

# Employee definition with approval limits
EMPLOYEES = [
    {"name": "Aditya Sharma", "role": "VP of Finance", "limit": 1000000},
    {"name": "Priya Patel", "role": "Finance Director", "limit": 200000},
    {"name": "Rajesh Verma", "role": "Accounts Manager", "limit": 50000},
    {"name": "Neha Gupta", "role": "Senior Accountant", "limit": 20000},
    {"name": "Amit Singh", "role": "Junior Accountant", "limit": 5000},
    {"name": "Sanjay Kumar", "role": "Operations Lead", "limit": 10000},
    {"name": "Kiran Rao", "role": "HR Manager", "limit": 15000},
    {"name": "Vikram Malhotra", "role": "IT Head", "limit": 100000},
    {"name": "Rahul Verma", "role": "Accounts Manager", "limit": 50000}  # Key approver for network fraud
]

CREATORS = [
    "Amit Singh", "Neha Gupta", "Rajesh Verma", "Sanjay Kumar", "Kiran Rao",
    "Rahul Sharma", "Sneha Reddy", "Anil Mehta", "Pooja Joshi"
]

PAYMENT_METHODS = ["Bank Transfer", "NEFT", "RTGS", "UPI", "Cash", "Credit Card"]

# ----------------------------------------------------
# 2. Generate Vendor Master
# ----------------------------------------------------
def generate_vendor_master():
    vendors_data = []
    
    # Standard helper for Indian GSTIN: 2 State Code, 10 PAN, 1 Entity Code, 1 Z, 1 Check Digit
    def make_gstin():
        pan = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5)) + \
              "".join(random.choices("0123456789", k=4)) + \
              random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return f"07{pan}1Z{random.choice('0123456789')}"

    # Set up shell network data explicitly
    shell_address = "Plot No. 42, Phase-III, Industrial Area, Okhla, New Delhi - 110020"
    shell_phone = "+91 98765 43210"
    shell_bank = "9182736455"
    shell_gstin = "07AAACK6188A1Z5"
    
    network_shell_vendors = {
        "Krishna Trading Co.": {
            "status": "Approved", 
            "reg_date": "2024-04-12",
            "gstin": shell_gstin
        },
        "KTC Enterprises": {
            "status": "Unapproved", 
            "reg_date": "2024-04-15",
            "gstin": "07AAACK6188A2Z6"  # Similar PAN state part
        },
        "K Trading Solutions": {
            "status": "Approved", 
            "reg_date": "2024-04-14",
            "gstin": "07AAACK6188A3Z7"
        }
    }
    
    for v in ALL_VENDORS:
        if v in network_shell_vendors:
            info = network_shell_vendors[v]
            vendors_data.append({
                "vendor_name": v,
                "gstin": info["gstin"],
                "address": shell_address,
                "phone_number": shell_phone,
                "bank_account": shell_bank,
                "status": info["status"],
                "registration_date": info["reg_date"]
            })
        else:
            status = "Approved" if v in APPROVED_VENDORS else "Unapproved"
            reg_date = fake.date_between(start_date="-3y", end_date="-1m").isoformat()
            vendors_data.append({
                "vendor_name": v,
                "gstin": make_gstin(),
                "address": fake.address().replace("\n", ", "),
                "phone_number": f"+91 {random.randint(70000, 99999)} {random.randint(10000, 99999)}",
                "bank_account": str(random.randint(1000000000, 9999999999)),
                "status": status,
                "registration_date": reg_date
            })
            
    df_vendors = pd.DataFrame(vendors_data)
    df_vendors.to_csv("data/vendor_master.csv", index=False)
    print(f"Generated data/vendor_master.csv with {len(df_vendors)} vendors.")
    return df_vendors

# ----------------------------------------------------
# 3. Generate Transactions
# ----------------------------------------------------
def generate_transactions():
    total_txns = 10000
    fraud_txns = 200
    normal_txns = total_txns - fraud_txns
    
    start_date = datetime.date(2025, 4, 1)
    end_date = datetime.date(2026, 3, 31)
    date_range = (end_date - start_date).days
    
    txns = []
    
    # Helper: generate log-normal amounts (realistic for business expenditures)
    # Mean around ₹25,000, but with a wide spread
    def make_normal_amount():
        val = np.random.lognormal(mean=9.5, sigma=1.2)  # exp(9.5) ~ ₹13,359
        return round(max(500.0, min(val, 2000000.0)), 2)

    # Helper: select approver appropriate for amount
    def get_valid_approver(amount):
        valid_apps = [e for e in EMPLOYEES if e["limit"] >= amount]
        if not valid_apps:
            valid_apps = [EMPLOYEES[0]]  # VP of Finance default
        return random.choice(valid_apps)["name"]

    # Helper: random business-hours time
    def make_normal_time():
        # 85% during 9am - 6pm
        if random.random() < 0.85:
            hour = random.randint(9, 17)
        else:
            hour = random.choice([7, 8, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6])
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        return datetime.time(hour, minute, second).isoformat()

    # Create normal transactions
    print("Generating normal transactions...")
    for i in range(normal_txns):
        amount = make_normal_amount()
        date = start_date + datetime.timedelta(days=random.randint(0, date_range))
        time_str = make_normal_time()
        vendor = random.choice(APPROVED_VENDORS)
        
        # Payment method distribution
        if amount > 100000:
            method = random.choice(["Bank Transfer", "NEFT", "RTGS"])
        elif amount > 20000:
            method = random.choice(["Bank Transfer", "NEFT", "UPI", "Credit Card"])
        else:
            method = random.choice(PAYMENT_METHODS)
            
        creator = random.choice(CREATORS)
        approver = get_valid_approver(amount)
        # Ensure creator and approver are not the same (Segregation of Duties)
        while creator == approver:
            creator = random.choice(CREATORS)
            
        head = random.choice(ACCOUNT_HEADS)
        
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": date.isoformat(),
            "time": time_str,
            "vendor_name": vendor,
            "amount": amount,
            "payment_method": method,
            "created_by": creator,
            "approved_by": approver,
            "account_head": head,
            "is_fraud": False,
            "fraud_type": "none"
        })

    # ----------------------------------------------------
    # Injected Fraud Cases (40 transactions each = 200 total)
    # ----------------------------------------------------
    print("Injecting fraud cases...")
    
    # 1. Duplicate Payments (40 transactions, i.e., 20 duplicate instances)
    # We will pick 20 already generated transactions and duplicate them with small offsets.
    duplicate_indices = random.sample(range(normal_txns), 20)
    for idx in duplicate_indices:
        orig = txns[idx]
        orig_date = datetime.date.fromisoformat(orig["date"])
        
        # Duplicate date within 30 days (1 to 20 days later)
        dup_date = orig_date + datetime.timedelta(days=random.randint(1, 20))
        # Ensure it fits within our period limit
        if dup_date > end_date:
            dup_date = orig_date - datetime.timedelta(days=random.randint(1, 20))
            
        dup_time = datetime.time(random.randint(9, 17), random.randint(0, 59), random.randint(0, 59)).isoformat()
        
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": dup_date.isoformat(),
            "time": dup_time,
            "vendor_name": orig["vendor_name"],
            "amount": orig["amount"],
            "payment_method": orig["payment_method"],
            "created_by": orig["created_by"],
            "approved_by": orig["approved_by"],
            "account_head": orig["account_head"],
            "is_fraud": True,
            "fraud_type": "duplicate"
        })

    # 2. Round Number Payments (40 transactions)
    # Large perfect round numbers (e.g., ₹50,000, ₹1,00,000, ₹5,00,000)
    round_amounts = [50000.0, 100000.0, 200000.0, 500000.0, 1000000.0]
    for _ in range(40):
        amount = random.choice(round_amounts)
        date = start_date + datetime.timedelta(days=random.randint(0, date_range))
        time_str = make_normal_time()
        # 50% to unapproved, 50% to approved
        vendor = random.choice(UNAPPROVED_VENDORS) if random.random() < 0.5 else random.choice(APPROVED_VENDORS)
        method = random.choice(["Bank Transfer", "NEFT", "RTGS", "Cash"]) # Cash for round numbers is high fraud risk
        creator = random.choice(CREATORS)
        approver = get_valid_approver(amount)
        if creator == approver:
            creator = random.choice(CREATORS)
        head = random.choice(ACCOUNT_HEADS)
        
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": date.isoformat(),
            "time": time_str,
            "vendor_name": vendor,
            "amount": amount,
            "payment_method": method,
            "created_by": creator,
            "approved_by": approver,
            "account_head": head,
            "is_fraud": True,
            "fraud_type": "round_number"
        })

    # 3. Unapproved Vendor Payments (40 transactions)
    # Payments sent to unapproved vendors
    for _ in range(40):
        amount = make_normal_amount()
        date = start_date + datetime.timedelta(days=random.randint(0, date_range))
        time_str = make_normal_time()
        vendor = random.choice(UNAPPROVED_VENDORS)
        method = random.choice(PAYMENT_METHODS)
        creator = random.choice(CREATORS)
        approver = get_valid_approver(amount)
        if creator == approver:
            creator = random.choice(CREATORS)
        head = random.choice(ACCOUNT_HEADS)
        
        # In this specific fraud type, we also want to simulate the shell network activity
        # If the vendor is KTC Enterprises (part of shell network), let's ensure it's approved by Rahul Verma
        if vendor == "KTC Enterprises":
            approver = "Rahul Verma"
            head = "Consulting Fees"
            amount = round(random.uniform(50000, 120000), 2)
            
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": date.isoformat(),
            "time": time_str,
            "vendor_name": vendor,
            "amount": amount,
            "payment_method": method,
            "created_by": creator,
            "approved_by": approver,
            "account_head": head,
            "is_fraud": True,
            "fraud_type": "unapproved_vendor"
        })

    # 4. Off-Hours & Weekend Anomalies (40 transactions)
    # High-value payments made late at night or on weekends
    for _ in range(40):
        amount = round(random.uniform(150000.0, 800000.0), 2)
        # Select weekend date (Saturday or Sunday)
        date = start_date + datetime.timedelta(days=random.randint(0, date_range))
        while date.weekday() not in [5, 6]:
            date = start_date + datetime.timedelta(days=random.randint(0, date_range))
            
        # Select late-night time (12 AM to 5 AM)
        hour = random.randint(0, 4)
        time_str = datetime.time(hour, random.randint(0, 59), random.randint(0, 59)).isoformat()
        
        vendor = random.choice(APPROVED_VENDORS)
        method = random.choice(["Cash", "UPI", "NEFT"]) # Cash/UPI for large amounts is highly anomalous
        creator = random.choice(CREATORS)
        approver = get_valid_approver(amount)
        if creator == approver:
            creator = random.choice(CREATORS)
        head = random.choice(ACCOUNT_HEADS)
        
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": date.isoformat(),
            "time": time_str,
            "vendor_name": vendor,
            "amount": amount,
            "payment_method": method,
            "created_by": creator,
            "approved_by": approver,
            "account_head": head,
            "is_fraud": True,
            "fraud_type": "off_hours"
        })

    # 5. Segregation of Duties (SoD) Violations (40 transactions)
    # Creator and approver are the exact same person
    for _ in range(40):
        amount = make_normal_amount()
        date = start_date + datetime.timedelta(days=random.randint(0, date_range))
        time_str = make_normal_time()
        vendor = random.choice(APPROVED_VENDORS)
        method = random.choice(PAYMENT_METHODS)
        
        # Pick someone who has approval limit and can also create (e.g. Rajesh, Neha, Priya)
        eligible_so_d = [e for e in EMPLOYEES if e["name"] in CREATORS and e["limit"] >= amount]
        if not eligible_so_d:
            eligible_so_d = [e for e in EMPLOYEES if e["name"] in CREATORS]
            
        person = random.choice(eligible_so_d)["name"]
        head = random.choice(ACCOUNT_HEADS)
        
        txns.append({
            "txn_id": f"TXN-{len(txns) + 1:05d}",
            "date": date.isoformat(),
            "time": time_str,
            "vendor_name": vendor,
            "amount": amount,
            "payment_method": method,
            "created_by": person,
            "approved_by": person, # SoD violation!
            "account_head": head,
            "is_fraud": True,
            "fraud_type": "segregation_of_duties"
        })

    # Shuffle the transactions so the fraud is hidden inside
    random.shuffle(txns)
    
    # Re-assign transaction IDs sequentially from TXN-00001 to TXN-10000
    for idx, txn in enumerate(txns):
        txn["txn_id"] = f"TXN-{idx+1:05d}"
        
    df_txns = pd.DataFrame(txns)
    df_txns.to_csv("data/transactions_clean.csv", index=False)
    print(f"Generated data/transactions_clean.csv with {len(df_txns)} transactions.")
    return df_txns

# ----------------------------------------------------
# 4. Generate Messy Version of Transactions
# ----------------------------------------------------
def make_data_messy(df):
    df_messy = df.copy()
    
    # Formats to randomize dates:
    # 70% YYYY-MM-DD (standard)
    # 15% DD/MM/YYYY
    # 15% MM-DD-YYYY
    def mess_up_date(date_str):
        d = datetime.date.fromisoformat(date_str)
        r = random.random()
        if r < 0.70:
            return date_str
        elif r < 0.85:
            return d.strftime("%d/%m/%Y")
        else:
            return d.strftime("%m-%d-%Y")

    # Formats for amount:
    # 60% standard float as string
    # 20% with currency sign (₹)
    # 20% with commas and currency sign (e.g. ₹ 1,50,000.00)
    def mess_up_amount(amt):
        r = random.random()
        if r < 0.60:
            return str(amt)
        elif r < 0.80:
            return f"₹{amt}"
        else:
            # Format with Indian commas if possible or standard commas
            # Standard python locale-independent formatting:
            formatted_amt = f"{amt:,.2f}"
            return f"₹ {formatted_amt}"
            
    # Add leading/trailing spaces to string fields (20% chance)
    def mess_up_spaces(val):
        if not isinstance(val, str):
            return val
        if random.random() < 0.20:
            spaces_before = " " * random.randint(1, 3)
            spaces_after = " " * random.randint(1, 3)
            return f"{spaces_before}{val}{spaces_after}"
        return val

    # Introduce some missing values (1% chance for non-critical fields)
    def introduce_nulls(val, col):
        if col in ["txn_id", "amount", "is_fraud"]: # Critical fields shouldn't be null
            return val
        if random.random() < 0.01:
            return ""
        return val

    print("Creating messy version of transactions...")
    df_messy["date"] = df_messy["date"].apply(mess_up_date)
    df_messy["amount"] = df_messy["amount"].apply(mess_up_amount)
    
    for col in df_messy.columns:
        if col not in ["is_fraud"]:
            df_messy[col] = df_messy[col].apply(lambda x: mess_up_spaces(x))
            df_messy[col] = df_messy[col].apply(lambda x: introduce_nulls(x, col))
            
    df_messy.to_csv("data/transactions_messy.csv", index=False)
    print(f"Generated data/transactions_messy.csv with messy formatting for pipeline validation.")

# ----------------------------------------------------
# Main Execution
# ----------------------------------------------------
if __name__ == "__main__":
    print("=== Starting Synthetic Data Generation ===")
    generate_vendor_master()
    df_clean = generate_transactions()
    make_data_messy(df_clean)
    print("=== Finished Synthetic Data Generation Successfully ===")
