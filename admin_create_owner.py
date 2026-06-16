"""Create or update a business-owner dashboard account.

Usage:
    python admin_create_owner.py <email> <password> <company_id>

The email is stored lowercased; re-running for an existing email updates the
password and company assignment.
"""
from __future__ import annotations

import sys

import auth
from memory_db import OwnerUser, get_session, init_db


def create_owner(email: str, password: str, company_id: str) -> None:
    email = email.strip().lower()
    company_id = company_id.strip()
    init_db()
    with get_session() as session:
        owner = session.query(OwnerUser).filter(OwnerUser.email == email).first()
        if owner is None:
            owner = OwnerUser(email=email, password_hash=auth.hash_password(password), company_id=company_id)
            session.add(owner)
            action = "created"
        else:
            owner.password_hash = auth.hash_password(password)
            owner.company_id = company_id
            action = "updated"
    print(f"Owner {action}: {email} -> company_id={company_id}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    create_owner(sys.argv[1], sys.argv[2], sys.argv[3])
