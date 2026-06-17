from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from memory_db import ChatTurn, ConversationContext, UserMemory, get_session

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _row_to_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


if __name__ == "__main__":
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = EXPORT_DIR / f"memory_export_{stamp}.json"
    with get_session() as session:
        users = [_row_to_dict(row) for row in session.scalars(select(UserMemory)).all()]
        contexts = [_row_to_dict(row) for row in session.scalars(select(ConversationContext)).all()]
        turns = [_row_to_dict(row) for row in session.scalars(select(ChatTurn)).all()]

    for bucket in [users, contexts, turns]:
        for item in bucket:
            for key, value in list(item.items()):
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()

    with destination.open("w", encoding="utf-8") as fp:
        json.dump({"users": users, "contexts": contexts, "chat_turns": turns}, fp, ensure_ascii=False, indent=2)

    print(f"Exported memory to {destination}")
