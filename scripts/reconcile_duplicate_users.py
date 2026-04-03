"""One-time repair utility for reconciling duplicate local app_users identities."""

from __future__ import annotations

import argparse

from macmarket_trader.storage.db import SessionLocal, init_db
from macmarket_trader.storage.repositories import UserRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile duplicate app_users rows in local/dev DB.")
    parser.add_argument("--email", default="", help="Reconcile only this normalized email identity.")
    parser.add_argument("--external-id", default="", help="Preferred external auth id when --email is used.")
    args = parser.parse_args()

    init_db()
    repo = UserRepository(SessionLocal)

    if args.email.strip():
        merged = repo.reconcile_identity_duplicates(
            external_auth_user_id=args.external_id.strip() or f"invited::{args.email.strip().lower()}",
            email=args.email,
        )
        print("reconciled=1" if merged is not None else "reconciled=0")
        return 0

    merged_count = repo.reconcile_all_duplicate_users()
    print(f"merged_rows={merged_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
