"""One-time backfill: zero out the silently-auto-defaulted Lead Scout 10% on
legacy leads.

Before Phase 40.2, `create_lead` silently set `referral_commission_id` to the
master `is_default=true` Lead Scout row whenever the client omitted it. After
Phase 40.2, no referral is auto-applied — but historical leads still carry
`referral_commission_percent = 10.0` cached on the document.

This script finds those leads (referral_commission_percent == 10.0 AND no
explicit referrer link) and resets them to 0.0 so Finance reports show accurate
"no referral" leads.

Usage:
    python -m scripts.backfill_zero_referrals --dry-run
    python -m scripts.backfill_zero_referrals --commit

The dry-run prints a sample of affected leads + total count. The commit run
performs the update.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


def _connect():
    url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME')
    if not url or not db_name:
        print("ERROR: MONGO_URL and DB_NAME must be set in the environment.", file=sys.stderr)
        sys.exit(2)
    return AsyncIOMotorClient(url)[db_name]


async def run(dry_run: bool) -> int:
    db = _connect()

    # Match the same heuristic the user uses: silently-defaulted = no explicit
    # referrer linkage AND the cached percent is exactly 10.0. We deliberately
    # leave alone any lead that has a referrer chosen (sales_associate_id /
    # referrer_user_id / a non-default referral_commission_id), even if the
    # percent happens to be 10.0 (that would be legitimate Lead Scout).
    default_level = await db.referral_commissions.find_one(
        {"is_default": True, "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "percent": 1},
    )
    default_id = default_level["id"] if default_level else None

    base_filter = {
        "referral_commission_percent": 10.0,
        # No actual referrer chosen
        "$and": [
            {"$or": [{"sales_associate_id": None}, {"sales_associate_id": {"$exists": False}}]},
            {"$or": [{"referrer_user_id": None}, {"referrer_user_id": {"$exists": False}}]},
        ],
    }
    if default_id:
        # Either no level link OR the link points at the silently-set default level
        base_filter["$or"] = [
            {"referral_commission_id": None},
            {"referral_commission_id": {"$exists": False}},
            {"referral_commission_id": default_id},
        ]
    else:
        base_filter["$or"] = [
            {"referral_commission_id": None},
            {"referral_commission_id": {"$exists": False}},
        ]

    matching = await db.leads.count_documents(base_filter)
    sample = await db.leads.find(base_filter, {"_id": 0, "id": 1, "title": 1, "customer_name": 1, "deal_value": 1, "referral_commission_percent": 1}).limit(10).to_list(10)

    print(f"\n=== Backfill: zero-out silently-defaulted Lead Scout 10% ===")
    print(f"Default level on file: {default_level['name'] if default_level else '(none)'}")
    print(f"Matching leads: {matching}")
    if sample:
        print(f"\nSample (up to 10):")
        for s in sample:
            print(f"  - {s.get('id', '')[:8]} | {s.get('title', '')[:40]:40} | "
                  f"customer={s.get('customer_name', '')[:25]:25} | "
                  f"deal={s.get('deal_value')}")
    if not matching:
        print("\nNothing to backfill. ✅")
        return 0
    if dry_run:
        print(f"\n[DRY RUN] Would update {matching} lead(s) — referral_commission_percent: 10.0 → 0.0 "
              "and unset referral_commission_id if it points at the silently-set default.")
        return 0

    # Commit
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "$set": {
            "referral_commission_percent": 0.0,
            "updated_at": now_iso,
            "_backfill_zero_referrals_at": now_iso,
        },
        "$unset": {"referral_commission_id": ""},
    } if default_id else {
        "$set": {
            "referral_commission_percent": 0.0,
            "updated_at": now_iso,
            "_backfill_zero_referrals_at": now_iso,
        },
    }
    res = await db.leads.update_many(base_filter, update)
    print(f"\n✅ Updated {res.modified_count} lead(s).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Backfill: zero out silently-defaulted Lead Scout 10%")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Print what would change; make no writes.")
    g.add_argument("--commit", action="store_true", help="Apply the backfill.")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
