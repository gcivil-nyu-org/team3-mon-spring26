"""
Creates the application database if it doesn't already exist.
Runs as a container_command before migrate so EB deployments work
against a fresh RDS instance that has no initial database configured.
"""

import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2 not available, skipping DB creation")
    sys.exit(0)

db_name = os.environ.get("DB_NAME", "nomz_db")
db_user = os.environ.get("DB_USER", "postgres")
db_password = os.environ.get("DB_PASSWORD", "")
db_host = os.environ.get("DB_HOST", "localhost")
db_port = int(os.environ.get("DB_PORT", "5432"))

try:
    conn = psycopg2.connect(
        dbname="postgres",
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        connect_timeout=15,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database '{db_name}' created successfully")
    else:
        print(f"Database '{db_name}' already exists")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
