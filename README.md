# Bitwarden export browser

A small local Flask application to import an unencrypted Bitwarden JSON export into SQLite, then search and filter the entries in a browser. The detail view includes secret values, so treat the database and the running app like your vault.

## Setup

Python 3.10+ recommended. From this directory:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python import_export.py
.venv/bin/python app.py
```

Then open <http://127.0.0.1:5000>. The importer defaults to `bitwarden_export_20261120112316.json` in this directory and creates `bitwarden.sqlite3` beside it. To select another export/database:

```sh
.venv/bin/python import_export.py /path/to/export.json --db /path/to/vault.sqlite3
BITWARDEN_DB=/path/to/vault.sqlite3 .venv/bin/python app.py
```

Re-running the importer replaces the current folders and items. The application uses SQLite read-only mode and binds only to loopback by default; do not expose it to a public or shared network. There is no authentication, so anyone with access to your local browser session can view secrets.

## Security

Bitwarden JSON exports and this SQLite database contain **unencrypted passwords, notes, and other sensitive data**. Keep the files out of source control, restrict filesystem access, and delete exports/database securely when no longer needed. Run only on a trusted machine. Do not change the bind address to `0.0.0.0` or use this app as a network-facing service. Consider full-disk encryption and avoid importing a decrypted export on a shared computer.
