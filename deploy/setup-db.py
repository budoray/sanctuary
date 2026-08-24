"""Local Postgres setup for Sanctuary development (Windows/Linux).

Run: python deploy/setup-db.py
"""
from __future__ import annotations

import os
import subprocess
import sys

DB_NAME = "sanctuary"
DB_USER = "Budoray"
DB_PASS = "Budoray"


def run_psql(sql: str, db: str = "postgres") -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    subprocess.run(
        ["psql", "-U", DB_USER, "-d", db, "-c", sql],
        env=env,
        check=True,
    )


def main():
    try:
        run_psql(f"CREATE DATABASE {DB_NAME};")
        print(f"Created database {DB_NAME}.")
    except subprocess.CalledProcessError:
        print(f"Database {DB_NAME} may already exist; continuing.")

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(
                f"DATABASE_URL=postgresql://{DB_USER}:{DB_PASS}@localhost:5432/{DB_NAME}\n"
                f"TENSHIN_SECRET=dev-secret-change-me\n"
                f"TENSHIN_SITE_URL=http://localhost:10600\n"
                f"LOAD_HOST=127.0.0.1\n"
                f"LOAD_PORT=10600\n"
                f"COOKIE_SECURE=0\n"
                f"TENSHIN_DEV=1\n"
            )
        print("Created .env with dev settings.")
    else:
        print(".env already exists; not overwriting.")


if __name__ == "__main__":
    main()
