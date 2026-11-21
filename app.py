#!/usr/bin/env python3
"""Private local web interface for searching a Bitwarden export."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, abort, g, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BITWARDEN_DB", BASE_DIR / "bitwarden.sqlite3")).resolve()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "local-only-change-me")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        if not DB_PATH.exists():
            abort(503, description="Database not found. Run python import_export.py first.")
        g.db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def item_type(value: int) -> str:
    return {1: "Login", 2: "Secure note", 3: "Card", 4: "Identity"}.get(value, f"Type {value}")


@app.template_filter("item_type")
def item_type_filter(value: int) -> str:
    return item_type(value)


@app.get("/")
def index() -> str:
    db = get_db()
    query = request.args.get("q", "").strip()[:200]
    selected_type = request.args.get("type", "")
    folder_id = request.args.get("folder", "")
    favorite = request.args.get("favorite", "")
    page = max(1, min(request.args.get("page", 1, type=int) or 1, 100000))
    page_size = 40

    where: list[str] = []
    params: list[Any] = []
    if query:
        where.append("searchable LIKE ? ESCAPE '\\' COLLATE NOCASE")
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    if selected_type.isdigit():
        where.append("type = ?")
        params.append(int(selected_type))
    if folder_id:
        if folder_id == "none":
            where.append("folder_id IS NULL")
        else:
            where.append("folder_id = ?")
            params.append(folder_id)
    if favorite == "1":
        where.append("favorite = 1")
    condition = " WHERE " + " AND ".join(where) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM items{condition}", params).fetchone()[0]
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    rows = db.execute(
        f"SELECT id,name,type,favorite,folder_id,username,uri,notes,creation_date,revision_date "
        f"FROM items{condition} ORDER BY name COLLATE NOCASE, id LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    folders = db.execute("SELECT id,name FROM folders ORDER BY name COLLATE NOCASE").fetchall()
    types = db.execute("SELECT DISTINCT type FROM items ORDER BY type").fetchall()
    return render_template(
        "index.html", items=rows, folders=folders, types=types, q=query,
        selected_type=selected_type, selected_folder=folder_id, favorite=favorite,
        total=total, page=page, page_count=page_count,
    )


@app.get("/item/<item_id>")
def item_detail(item_id: str) -> str:
    row = get_db().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        abort(404)
    data = json.loads(row["data_json"])
    folder = None
    if row["folder_id"]:
        folder = get_db().execute("SELECT name FROM folders WHERE id = ?", (row["folder_id"],)).fetchone()
    return render_template("item.html", item=data, folder=folder["name"] if folder else None)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'"
    return response


if __name__ == "__main__":
    # Bind to loopback only. Do not expose this unauthenticated vault UI to a network.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
