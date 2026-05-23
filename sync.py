import argparse
import csv
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

# Ensure project root is in path for imports
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.mappers.db_import_orchestrator import DbImportOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Sync Peptide CSV data to PostgreSQL")
    parser.add_argument("--csv", required=False, help="Path to the CSV file")
    parser.add_argument("--delete", metavar="SLUG", help="Delete a peptide and its related data by slug")
    parser.add_argument("--limit",default=100, help="limit the insertion list")
    
    args = parser.parse_args()

    orchestrator = DbImportOrchestrator()

    if args.delete:
        from src.infrastructure.db_manager import DbManager
        db = DbManager(os.getenv("DATABASE_URL"))
        try:
            db.delete_peptide_data(args.delete)
        finally:
            db.close()
        return

    # Read CSV
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found at {args.csv}")
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with open(args.csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i,row in enumerate(reader):
            rows.append(row)
            if i > int(args.limit):
                break

    print(f"Read {len(rows)} rows from {args.csv}")
    
    # Sync to DB
    print("Starting sync...")
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows)
    print("Sync completed successfully.")

if __name__ == "__main__":
    main()
