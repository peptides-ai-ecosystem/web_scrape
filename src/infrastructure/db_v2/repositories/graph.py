"""
GraphRepositoryV2 — Fixed: peptide_graph has no UNIQUE(peptide_id, am_id, time_range).

Falls back to SELECT → INSERT/UPDATE inside the caller's single transaction.
"""
import json
from typing import Any, Dict, List
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class GraphRepositoryV2(BaseRepositoryV2):

    def upsert(self, peptide_id: int, am_id: int, graph_data: Dict[str, Any]):
        existing = self.execute_one(
            "SELECT id FROM peptide_graph WHERE peptide_id = %s AND administration_method_id = %s AND time_range = %s",
            (peptide_id, am_id, graph_data["time_range"]),
        )

        fields = {
            "peak_concentration": graph_data.get("peak_concentration"),
            "half_life":          graph_data.get("half_life"),
            "cleared_percentage": graph_data.get("cleared_percentage"),
            "path_data":          graph_data.get("path_data"),
            "markers":            graph_data.get("markers"),
            "points":             graph_data.get("points"),
            "x_axis_labels":      graph_data.get("x_axis_labels"),
            "y_axis_labels":      graph_data.get("y_axis_labels"),
            "legend":             graph_data.get("legend"),
        }

        if existing:
            graph_id = existing["id"]
            set_clause = ", ".join([f"{col} = %s" for col in fields]) + ", updated_at = NOW()"
            self.execute_write(
                f"UPDATE peptide_graph SET {set_clause} WHERE id = %s",
                list(fields.values()) + [graph_id],
            )
            self.log_op("UPDATE_GRAPH", "peptide_graph",
                        f"Peptide {peptide_id}/method {am_id}/range '{graph_data['time_range']}'")
        else:
            cols = ["peptide_id", "administration_method_id", "time_range"] + list(fields.keys())
            vals = [peptide_id, am_id, graph_data["time_range"]] + list(fields.values())
            graph_id = self.execute_returning(
                f"INSERT INTO peptide_graph ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
                vals,
            )
            self.log_op("INSERT_GRAPH", "peptide_graph",
                        f"Peptide {peptide_id}/method {am_id}/range '{graph_data['time_range']}' (ID: {graph_id})")

    def get_methods_for_peptide(self, peptide_id: int) -> List[Dict[str, Any]]:
        rows = self.execute_all("""
            SELECT DISTINCT am.id, am.name
            FROM peptide_graph pg
            JOIN administration_methods am ON pg.administration_method_id = am.id
            WHERE pg.peptide_id = %s
            ORDER BY am.name
        """, (peptide_id,))
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    def get_visualization_data(self, peptide_id: int, method_name: str = "Injectable") -> Dict[str, Any]:
        result = {}
        peptide_row = self.execute_one("SELECT name FROM peptides WHERE id = %s", (peptide_id,))
        result["peptide_name"] = peptide_row["name"] if peptide_row else "Unknown"
        result["administration_method"] = method_name

        am_row = self.execute_one("SELECT id FROM administration_methods WHERE name = %s", (method_name,))
        am_id = am_row["id"] if am_row else 6

        rows = self.execute_all(
            "SELECT * FROM peptide_graph WHERE peptide_id = %s AND administration_method_id = %s ORDER BY time_range",
            (peptide_id, am_id),
        )

        def _parse(val, default):
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return val
            try:
                return json.loads(val) if val else default
            except (json.JSONDecodeError, TypeError):
                return default

        for row in rows:
            tr = row["time_range"]
            result[tr] = {
                "metadata": {"peak": row.get("peak_concentration", ""), "half_life": row.get("half_life", ""), "cleared": row.get("cleared_percentage", "")},
                "path_data": row.get("path_data", ""),
                "markers": _parse(row.get("markers"), []),
                "points": _parse(row.get("points"), []),
                "x_labels": _parse(row.get("x_axis_labels"), []),
                "y_labels": _parse(row.get("y_axis_labels"), []),
                "legend": _parse(row.get("legend"), {}),
            }
        return result
