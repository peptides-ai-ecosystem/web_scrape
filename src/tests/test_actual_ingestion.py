import argparse
import csv
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from .env
load_dotenv(os.path.join(project_root, ".env"))

from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.infrastructure.db_manager import DbManager

def test_actual_ingestion(db_url: str, csv_path: str, limit: int):
    print(f"\n{'='*60}")
    print(f"STARTING ACTUAL INGESTION TEST")
    print(f"DB URL: {db_url.split('@')[-1] if '@' in db_url else db_url}") # Hide password
    print(f"CSV Source: {csv_path}")
    print(f"Row Limit: {limit}")
    print(f"{'='*60}\n")

    if not os.path.exists(csv_path):
        # Fallback if running from root or elsewhere
        abs_csv_path = os.path.join(project_root, csv_path)
        if not os.path.exists(abs_csv_path):
            print(f"Error: CSV file not found at {csv_path} or {abs_csv_path}")
            return
        csv_path = abs_csv_path

    # 1. Read CSV
    print(f"[STEP 1] Reading CSV file...")
    rows = []
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if len(rows) >= limit:
                    break
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    print(f"  Successfully read {len(rows)} row(s) for testing.\n")

    # 2. Setup Orchestrator
    print(f"[STEP 2] Initializing Orchestrator...")
    orchestrator = DbImportOrchestrator()

    # 3. Process Rows
    print(f"[STEP 3] Starting Ingestion...")
    try:
        orchestrator.sync_to_db(db_url, rows)
        print(f"\n[SUCCESS] Ingested {len(rows)} rows into the actual database.")
    except Exception as e:
        print(f"\n[FAILURE] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"INGESTION TEST COMPLETED")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Ingestion with Actual DB and CSV")
    parser.add_argument("--url", help="PostgreSQL connection URL (overrides .env DATABASE_URL)")
    parser.add_argument("--csv", default="output_v6/pep_pedia_master.csv", help="Path to the CSV file")
    parser.add_argument("--limit", type=int, default=1, help="Limit the number of rows to process")
    
    args = parser.parse_args()

    # Priority: 1. CLI Arg, 2. Env Var, 3. Error
    db_url = args.url or os.getenv("DATABASE_URL")
    
    if not db_url:
        print("Error: No database URL provided.")
        print("Please provide it via --url or set DATABASE_URL in your .env file.")
        sys.exit(1)

    test_actual_ingestion(db_url, args.csv, args.limit)
