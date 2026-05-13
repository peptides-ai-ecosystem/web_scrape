import os
import json
import sys
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()

from src.infrastructure.db_manager import DbManager
from src.mappers.db_import_orchestrator import DbImportOrchestrator

def test_graph_sync():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set.")
        return

    orchestrator = DbImportOrchestrator()
    db = DbManager(db_url)

    # 1. Prepare sample row
    sample_graph_data = {
        "24h": {
            "peak": "2.5 mcg/mL",
            "half_life": "4.2 hours",
            "cleared": "95%",
            "points": [{"x": 0.0, "y": 0.0}, {"x": 2.0, "y": 2.5}, {"x": 24.0, "y": 0.1}],
            "x_axis_labels": [{"pos": 0.0, "label": "0h"}, {"pos": 12.0, "label": "12h"}],
            "y_axis_labels": [{"pos": 0.0, "label": "0.0"}, {"pos": 2.5, "label": "2.5"}]
        }
    }

    test_row = {
        "Peptide_Name": "TestPeptide",
        "Full_Name": "Test Peptide for Graph",
        "Method": "Injection",
        "URL": "https://example.com/test",
        "slug": "test-peptide",
        "graph_data_json": json.dumps(sample_graph_data)
    }

    print(f"Syncing test row for {test_row['Peptide_Name']}...")
    
    try:
        # We need a peptide with this slug in the DB first
        peptide_payload = {
            "name": test_row["Peptide_Name"],
            "slug": test_row["slug"],
            "synonyms": test_row["Full_Name"]
        }
        peptide_id = db.upsert_peptide_fill_nulls(peptide_payload)
        print(f"Peptide ID: {peptide_id}")

        # Map and sync
        payload = orchestrator.map_row(test_row)
        orchestrator._sync_relations(db, peptide_id, payload["relations"], payload["protocols"], payload["graph_data"])
        
        print("Sync call finished. Verifying database...")

        # Verify in DB
        with db.connect().cursor() as cur:
            cur.execute("SELECT * FROM peptide_graph_data WHERE peptide_id = %s", (peptide_id,))
            rows = cur.fetchall()
            
            if rows:
                print(f"Verification SUCCESS: Found {len(rows)} graph data records.")
                for row in rows:
                    print(f" - Range: {row['time_range']}, Peak: {row['peak_concentration']}")
            else:
                print("Verification FAILED: No graph data found in table.")

    except Exception as e:
        print(f"An error occurred during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_graph_sync()
