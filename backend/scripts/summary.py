"""Emit a summary of what is currently stored (debug/audit helper)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.models.classification import Classification  # noqa: E402
from app.models.review_item import ReviewItem  # noqa: E402

logger = get_logger("summary")


def main() -> None:
    configure_logging()
    with SessionLocal() as db:
        txns = db.query(Transaction).count()
        classified = db.query(Classification).count()
        review = db.query(ReviewItem).filter(ReviewItem.status == "pending").count()
        print(f"transactions       : {txns}")
        print(f"classified         : {classified}")
        print(f"pending review     : {review}")
        months = set()
        for (d,) in db.query(Transaction.date).all():
            months.add(d.strftime("%Y-%m"))
        print("months             :", sorted(months))


if __name__ == "__main__":
    main()