"""Graph repository for peptide graph data operations."""
from typing import Dict, Any, Optional, List
from src.infrastructure.db.base_repository import BaseRepository
import json


class GraphRepository(BaseRepository):
    """Repository for peptide graph data (pharmacokinetics) operations."""

    def upsert(self, peptide_id: int, am_id: int, graph_data: Dict[str, Any]):
        """Upserts pharmacokinetics graph data."""
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT id FROM peptide_graph WHERE peptide_id = %s AND administration_method_id = %s AND time_range = %s",
                (peptide_id, am_id, graph_data['time_range'])
            )
            row = cur.fetchone()
            
            fields = {
                'peak_concentration': graph_data.get('peak_concentration'),
                'half_life': graph_data.get('half_life'),
                'cleared_percentage': graph_data.get('cleared_percentage'),
                'path_data': graph_data.get('path_data'),
                'markers': graph_data.get('markers'),
                'points': graph_data.get('points'),
                'x_axis_labels': graph_data.get('x_axis_labels'),
                'y_axis_labels': graph_data.get('y_axis_labels'),
                'legend': graph_data.get('legend'),
            }
            
            if row:
                graph_id = row['id']
                set_clause = ", ".join([f"{col} = %s" for col in fields.keys()])
                set_clause += ", updated_at = NOW()"
                params = list(fields.values()) + [graph_id]
                cur.execute(f"UPDATE peptide_graph SET {set_clause} WHERE id = %s", params)
                self._commit()
                self.log_operation("UPDATE_GRAPH", "peptide_graph", 
                    f"Peptide {peptide_id}: '{graph_data['time_range']}'")
            else:
                cols = ["peptide_id", "administration_method_id", "time_range"] + list(fields.keys())
                vals = [peptide_id, am_id, graph_data['time_range']] + list(fields.values())
                placeholders = ", ".join(["%s"] * len(vals))
                cur.execute(
                    f"INSERT INTO peptide_graph ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
                    vals
                )
                graph_id = cur.fetchone()['id']
                self._commit()
                self.log_operation("INSERT_GRAPH", "peptide_graph", 
                    f"Peptide {peptide_id}: '{graph_data['time_range']}' (ID: {graph_id})")

    def get_methods_for_peptide(self, peptide_id: int) -> List[Dict[str, Any]]:
        """Get all available administration methods for a peptide."""
        rows = self.execute_all("""
            SELECT DISTINCT am.id, am.name
            FROM peptide_graph pg
            JOIN administration_methods am ON pg.administration_method_id = am.id
            WHERE pg.peptide_id = %s
            ORDER BY am.name
        """, (peptide_id,))
        return [{"id": row['id'], "name": row['name']} for row in rows]

    def get_visualization_data(self, peptide_id: int, method_name: str = "Injectable") -> Dict[str, Any]:
        """
        Fetch and format graph data for frontend visualization.

        Returns data in visualization format with peptide and method metadata.
        """
        result = {}
        with self.get_cursor() as cur:
            # Get peptide name
            cur.execute("SELECT name FROM peptides WHERE id = %s", (peptide_id,))
            peptide_row = cur.fetchone()
            result['peptide_name'] = peptide_row['name'] if peptide_row else 'Unknown'
            result['administration_method'] = method_name

            # Get administration method ID
            cur.execute("SELECT id FROM administration_methods WHERE name = %s", (method_name,))
            am_row = cur.fetchone()
            am_id = am_row['id'] if am_row else 6  # Default to Injectable (ID 6)

            # Fetch all graph records for this peptide
            cur.execute(
                "SELECT * FROM peptide_graph WHERE peptide_id = %s AND administration_method_id = %s ORDER BY time_range",
                (peptide_id, am_id)
            )
            rows = cur.fetchall()

            for row in rows:
                time_range = row['time_range']

                # Helper function to parse JSON
                def parse_json(val, default):
                    if val is None:
                        return default
                    if isinstance(val, (list, dict)):
                        return val  # Already parsed by psycopg2
                    try:
                        return json.loads(val) if val else default
                    except (json.JSONDecodeError, TypeError):
                        return default

                result[time_range] = {
                    "metadata": {
                        "peak": row.get('peak_concentration', ''),
                        "half_life": row.get('half_life', ''),
                        "cleared": row.get('cleared_percentage', '')
                    },
                    "path_data": row.get('path_data', ''),
                    "markers": parse_json(row.get('markers'), []),
                    "points": parse_json(row.get('points'), []),
                    "x_labels": parse_json(row.get('x_axis_labels'), []),
                    "y_labels": parse_json(row.get('y_axis_labels'), []),
                    "legend": parse_json(row.get('legend'), {})
                }

        return result

    def get_by_peptide_and_method(self, peptide_id: int, am_id: int) -> List[Dict[str, Any]]:
        """Get all graph records for a peptide and administration method."""
        return self.execute_all(
            "SELECT * FROM peptide_graph WHERE peptide_id = %s AND administration_method_id = %s",
            (peptide_id, am_id)
        )
