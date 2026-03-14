"""
Database migration script for v2.0.

Adds new columns to the posts table.
"""

import sqlite3
import os
from pathlib import Path


def migrate_database(db_path: str = "./data/tg_poster.db"):
    """Add new v2.0 columns to posts table."""

    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(posts)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = [
        ("post_type", "VARCHAR(50) DEFAULT 'breaking'"),
        ("confidence_score", "FLOAT DEFAULT 0.0"),
        ("quality_score", "FLOAT DEFAULT 0.0"),
        ("editor_score", "FLOAT DEFAULT 0.0"),
        ("verification_score", "FLOAT DEFAULT 0.0"),
        ("needs_review", "BOOLEAN DEFAULT 0"),
        ("post_title", "VARCHAR(200)"),
        ("post_hook", "TEXT"),
        ("post_body", "TEXT"),
        ("post_tldr", "VARCHAR(300)"),
        ("post_analysis", "TEXT"),
        ("post_key_facts", "TEXT"),
        ("post_sources", "TEXT"),
        ("post_hashtags", "TEXT"),
        ("media_prompt", "TEXT"),
        ("source_count", "INTEGER DEFAULT 0"),
        ("source_tiers", "VARCHAR(100)"),
        ("pipeline_version", "VARCHAR(50) DEFAULT '1.0'"),
    ]

    added = []
    skipped = []

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                sql = f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                added.append(col_name)
                print(f"Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"Error adding {col_name}: {e}")
                skipped.append(col_name)
        else:
            skipped.append(col_name)
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()

    print(f"\nMigration complete!")
    print(f"Added: {len(added)} columns")
    print(f"Skipped: {len(skipped)} columns (already exist)")

    return added


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "./data/tg_poster.db"
    print(f"Migrating database: {db_path}")
    migrate_database(db_path)
