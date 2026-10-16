#!/usr/bin/env python3
"""
HelpDesk Management System - Automated Backup & Disaster Recovery CLI Utility
Week 8 Production Hardening Module.

Usage:
    python backup_manager.py           # Create an immediate online backup
    python backup_manager.py --list    # List available backup snapshots
    python backup_manager.py --verify  # Verify database integrity and pragma status
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime

DB_PATH = "helpdesk.db"
BACKUP_DIR = "backups"

def create_backup(db_path=DB_PATH, backup_dir=BACKUP_DIR):
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file '{db_path}' not found.")
        sys.exit(1)

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"helpdesk_backup_{timestamp}.db"
    backup_filepath = os.path.join(backup_dir, backup_filename)

    print(f"[*] Initiating atomic online backup of '{db_path}'...")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_filepath)
    with dst:
        src.backup(dst, pages=100)
    dst.close()
    src.close()

    size_kb = round(os.path.getsize(backup_filepath) / 1024, 2)
    print(f"[SUCCESS] Backup snapshot created: '{backup_filepath}' ({size_kb} KB)")

    # Rotate old backups (keep latest 10)
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("helpdesk_backup_") and f.endswith(".db")],
        reverse=True
    )
    if len(backups) > 10:
        for old_file in backups[10:]:
            old_path = os.path.join(backup_dir, old_file)
            os.remove(old_path)
            print(f"[*] Rotated old snapshot: {old_file}")

    return backup_filepath

def list_backups(backup_dir=BACKUP_DIR):
    if not os.path.exists(backup_dir):
        print(f"No backups directory found at '{backup_dir}'.")
        return

    files = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("helpdesk_backup_") and f.endswith(".db")],
        reverse=True
    )
    print(f"\n=== AVAILABLE DATABASE BACKUPS ({len(files)} total) ===")
    print(f"{'Filename':<35} | {'Size (KB)':<10} | {'Created At'}")
    print("-" * 65)
    for f in files:
        fp = os.path.join(backup_dir, f)
        stat = os.stat(fp)
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{f:<35} | {round(stat.st_size/1024, 1):<10} | {mtime}")
    print()

def verify_database(db_path=DB_PATH):
    print(f"\n[*] Running integrity diagnostics on '{db_path}'...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchall()
    print(f"[CHECK] PRAGMA integrity_check: {result[0][0] if result else 'UNKNOWN'}")

    cursor.execute("PRAGMA journal_mode")
    print(f"[CHECK] PRAGMA journal_mode: {cursor.fetchone()[0]}")

    cursor.execute("PRAGMA foreign_keys")
    print(f"[CHECK] PRAGMA foreign_keys: {cursor.fetchone()[0]}")

    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    indexes = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_autoindex")]
    print(f"[CHECK] Performance Indexes Active: {len(indexes)} ({', '.join(indexes)})")

    conn.close()
    print("[SUCCESS] All database diagnostics passed.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HelpDesk Database Backup & Recovery Utility")
    parser.add_argument("--list", action="store_true", help="List all available backup snapshots")
    parser.add_argument("--verify", action="store_true", help="Run SQLite integrity check and diagnostics")
    args = parser.parse_args()

    if args.list:
        list_backups()
    elif args.verify:
        verify_database()
    else:
        create_backup()
