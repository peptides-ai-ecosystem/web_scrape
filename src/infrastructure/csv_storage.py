import pandas as pd
from typing import List
from tqdm import tqdm
from src.core.models import PeptideData
from src.core.interfaces import IStorage
import json
from dataclasses import asdict
from src.config import MASTER_CSV, log_debug, log_error
from typing import List, Dict, Any
import csv
import os

class CSVStorage(IStorage):
    def save(self, data: List[PeptideData]) -> None:
        try:
            log_debug(f"Starting CSV save operation for {len(data)} records", "csv_storage.py")
            rows = []
            for p_data in tqdm(data, desc="Processing records for CSV", unit="record", leave=False):
                row = {
                    "Peptide_Name": p_data.name,
                    "Full_Name": p_data.full_name,
                    "Method": p_data.method,
                    "URL": p_data.url
                }
                
                # Hero facts
                for fact in p_data.hero.facts:
                    col_name = fact.label.replace(" ", "_").lower()
                    row[col_name] = f"{fact.value} ({fact.extra})"
                
                # Quick guide
                for k, v in p_data.quick_guide.items():
                    col_name = f"quick_guide_{k.replace(' ', '_').lower()}"
                    row[col_name] = v
                
                # Community insights
                for k, v in p_data.community_insights.items():
                    row[k.replace(" ", "_").lower()] = v
                
                # Poll results
                for k, v in p_data.poll_results.items():
                    row[k.replace(" ", "_").lower()] = v
                
                # Sections
                for section in p_data.sections:
                    for k, v in section.items():
                        if v:
                            row[k] = v.strip()
                
                # Graph Data
                if p_data.graph_data:
                    # We store the full graph data as a JSON string in one column for simplicity in CSV
                    # or we could flatten it more if needed.
                    row["graph_data_json"] = json.dumps({k: asdict(v) for k, v in p_data.graph_data.items()})
                
                rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows)
                # Overwrite existing CSV on each save.
                df.to_csv(MASTER_CSV, index=False)
                log_debug(f"Successfully saved {len(rows)} rows to {MASTER_CSV} (overwrote previous)", "csv_storage.py")
                print(f"[INFO] Data overwrote {MASTER_CSV} with {len(rows)} rows")
        except Exception as e:
            error_msg = f"Failed to save CSV: {str(e)}"
            print(f"[ERROR] {error_msg}")
            log_error(error_msg, "csv_storage.py")

    def read(self) -> List[PeptideData]:
        """Read CSV file with optional row limit."""
        if not os.path.exists(MASTER_CSV):
            print(f"Error: CSV file not found at {MASTER_CSV}")
            return []
        rows: List[Dict[str, Any]] = []
        with open(MASTER_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Reading CSV file", unit="row"):
                rows.append(row)
        print(f"Read {len(rows)} rows from {MASTER_CSV}")
        return rows
