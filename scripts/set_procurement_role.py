"""Local operator utility; roles cannot be self-assigned through the API.

python -m scripts.set_procurement_role --email manager@example.com --role manager
"""
import argparse
from backend.app.config import DATABASE_URL
from backend.app.db import SessionLocal
from backend.app.models.auth import User

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    parser.add_argument('--role',required=True,choices=['auditor','manager','finance','security','admin'])
    args=parser.parse_args()
    with SessionLocal() as db:
        user=db.query(User).filter_by(email=args.email.lower()).first()
        if not user:
            raise SystemExit('Account not found. Sign in once before assigning its role.')
        user.role=args.role
        db.commit()
        print('Role updated for the specified account. Sign in again to refresh the displayed role.')
