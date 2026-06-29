import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from src.config import MASTER_CSV, log_debug, log_error
from src.core.interfaces import IStorage
from src.core.models import PeptideData

class CSVStorage(IStorage):
    def __init__(self, csv_path: Optional[Path] = None):
        self.csv_path = csv_path or MASTER_CSV

    def save(self, data: List[PeptideData]) -> None:
        try:
            log_debug(f"Starting CSV save operation for {len(data)} records to {self.csv_path}", "csv_storage.py")
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
                
                # Quick guide (may be empty if skipped in GRAPH_ONLY mode)
                for k, v in p_data.quick_guide.items():
                    col_name = f"quick_guide_{k.replace(' ', '_').lower()}"
                    row[col_name] = v
                
                # Community insights (may be empty if skipped in GRAPH_ONLY mode)
                for k, v in p_data.community_insights.items():
                    row[k.replace(" ", "_").lower()] = v
                
                # Poll results (may be empty if skipped in GRAPH_ONLY mode)
                for k, v in p_data.poll_results.items():
                    row[k.replace(" ", "_").lower()] = v
                
                # Sections (may be empty if skipped in GRAPH_ONLY mode)
                for section in p_data.sections:
                    for k, v in section.items():
                        if v:
                            row[k] = v.strip()
                
                # Graph Data (may be empty if skipped in CORE_ONLY mode)
                if p_data.graph_data:
                    row["graph_data_json"] = json.dumps({k: asdict(v) for k, v in p_data.graph_data.items()})
                
                rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(self.csv_path, index=False)
                log_debug(f"Successfully saved {len(rows)} rows to {self.csv_path} (overwrote previous)", "csv_storage.py")
                print(f"[INFO] Data overwrote {self.csv_path} with {len(rows)} rows")
        except Exception as e:
            error_msg = f"Failed to save CSV: {str(e)}"
            print(f"[ERROR] {error_msg}")
            log_error(error_msg, "csv_storage.py")

    def read(self) -> List[Dict[str, Any]]:
        """Read CSV file."""
        if not os.path.exists(self.csv_path):
            print(f"Error: CSV file not found at {self.csv_path}")
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Reading CSV file", unit="row"):
                rows.append(row)
        print(f"Read {len(rows)} rows from {self.csv_path}")
        return rows
