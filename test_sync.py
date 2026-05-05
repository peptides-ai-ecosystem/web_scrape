import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

# Ensure project root is in path
import os
import sys
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.mappers.db_import_orchestrator import DbImportOrchestrator

def test_sync_fill_nulls():
    orchestrator = DbImportOrchestrator()
    
    # Mock data
    row = {
        "Peptide_Name": "Test-Peptide",
        "Full_Name": "Full Name",
        "overview_what_is_test_peptide": "Description from CSV",
        "Method": "Injectable",
        "overview_key_benefits": "Benefit 1. Benefit 2",
        "side_effects_and_safety_side_effects_1": "Nausea"
    }
    
    # Mock existing DB record
    existing_record = {
        "id": 1,
        "slug": "test-peptide",
        "name": "Test-Peptide",
        "overview": None, # This should be updated
        "synonyms": "Existing Synonyms", # This should NOT be updated
        "mechanism_of_action": None
    }

    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
        
        # side_effect for fetchone: 
        # 1. get_peptide_by_slug -> existing record
        # 2. insert_lookup (administration_methods) -> id 1
        # 3. insert_lookup (benefits) -> id 1
        # 4. insert_lookup (side_effects) -> id 1
        mock_cursor.fetchone.side_effect = [
            existing_record, # get_peptide_by_slug
            {"id": 1}, # insert_lookup administration_methods
            {"id": 1}, # insert_lookup benefits
            {"id": 1}, # insert_lookup side_effects
            {"id": 1}, # protocol lookup
            {"id": 1}, # interaction lookup
            {"id": 1}, # indication lookup
            {"id": 1}, # reference lookup
        ]

        # Now run the sync
        orchestrator.sync_to_db("dbname=test", [row])
        
        # Verify UPDATE was called for 'overview' which was NULL in DB but present in CSV
        update_calls = [c for c in mock_cursor.execute.call_args_list if "UPDATE peptides SET" in c[0][0]]
        assert len(update_calls) > 0
        print(f"Verification: UPDATE query generated: {update_calls[0][0][0]}")
        assert "overview = %s" in update_calls[0][0][0]
        print("Verification: UPDATE correctly targeted NULL field 'overview'.")

if __name__ == "__main__":
    test_sync_fill_nulls()
