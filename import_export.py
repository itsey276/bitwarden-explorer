#!/usr/bin/env python3
"""Import a Bitwarden JSON export into a local SQLite database.

The export and resulting database contain unencrypted secrets. Keep both private.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_EXPORT = Path(__file__).with_name("bitwarden_export_20261120112316.json")
DEFAULT_DB = Path(__file__).with_name("bitwarden.sqlite3")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    type INTEGER NOT NULL DEFAULT 0,
    favorite INTEGER NOT NULL DEFAULT 0,
    folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
    username TEXT NOT NULL DEFAULT '',
    uri TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    searchable TEXT NOT NULL DEFAULT '',
    creation_date TEXT,
    revision_date TEXT,
    data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_items_folder ON items(folder_id);
CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
CREATE INDEX IF NOT EXISTS idx_items_favorite ON items(favorite);
"""


def import_export(export_path: Path, db_path: Path) -> tuple[int, int]:
    with export_path.open(encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError("Expected a Bitwarden JSON export with an items array")
    if document.get("encrypted"):
        raise ValueError("This export is encrypted; decrypt it with Bitwarden before importing")

    folders = document.get("folders") or []
    items = document["items"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        with db:
            db.execute("DELETE FROM items")
            db.execute("DELETE FROM folders")
            db.executemany(
                "INSERT INTO folders(id, name) VALUES (?, ?)",
                [(str(folder.get("id", "")), str(folder.get("name", "")))
                 for folder in folders if folder.get("id")],
            )
            rows = []
            for item in items:
                login = item.get("login") or {}
                uris = login.get("uris") or []
                uri_values = [str(entry.get("uri", "")) for entry in uris if entry.get("uri")]
                fields = item.get("fields") or []
                search_parts = [
                    str(item.get("name", "")), str(login.get("username", "")),
                    " ".join(uri_values), str(item.get("notes", "")),
                    " ".join(str(field.get("name", "")) + " " + str(field.get("value", ""))
                              for field in fields if isinstance(field, dict)),
                ]
                rows.append((
                    str(item.get("id") or ""), str(item.get("name") or ""),
                    int(item.get("type") or 0), int(bool(item.get("favorite"))),
                    item.get("folderId"), str(login.get("username") or ""),
                    "\n".join(uri_values), str(item.get("notes") or ""),
                    " ".join(search_parts), item.get("creationDate"), item.get("revisionDate"),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                ))
            db.executemany(
                """INSERT INTO items
                   (id,name,type,favorite,folder_id,username,uri,notes,searchable,
                    creation_date,revision_date,data_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows,
            )
    return len(items), len(folders)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", nargs="?", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    items, folders = import_export(args.export, args.db)
    print(f"Imported {items} items and {folders} folders into {args.db}")
    print("WARNING: This database contains unencrypted vault data. Protect it like the original export.")


if __name__ == "__main__":
    main()
