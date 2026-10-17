"""Graph repository for peptide graph data operations."""
from typing import Dict, Any, Optional, List
from app.repositories.base import BaseRepository
import json

# pep-pedia.org serves each peptide at /peptides/<slug>; the crawler follows
# exactly these links. The peptides table keeps no scraped URL, so the source
# link is derived from the slug the graph importer matched on.
PEP_PEDIA_PEPTIDE_URL = "https://pep-pedia.org/peptides/{slug}"

# One row per peptide that has PK curves: the methods available, how many
# curve rows exist, when the newest one was written, and a headline row
# (Injectable + 24h preferred, else the most recently written) for the
# half-life / peak / cleared summary.
PK_SUMMARY_SQL = """
    WITH headline AS (
        SELECT DISTINCT ON (pg.peptide_id)
            pg.peptide_id,
            am.name AS method,
            pg.half_life,
            pg.peak_concentration,
            pg.cleared_percentage,
            pg.action_type
        FROM peptide_graph pg
        LEFT JOIN administration_methods am ON am.id = pg.administration_method_id
        ORDER BY pg.peptide_id,
                 (am.name = 'Injectable') DESC NULLS LAST,
                 (pg.time_range = '24h') DESC NULLS LAST,
                 COALESCE(pg.updated_at, pg.created_at) DESC NULLS LAST
    )
    SELECT p.id,
           p.name,
           p.slug,
           ARRAY_REMOVE(ARRAY_AGG(DISTINCT am.name), NULL) AS methods,
           COUNT(pg.id) AS curve_count,
           MAX(COALESCE(pg.updated_at, pg.created_at)) AS last_updated,
           h.method AS headline_method,
           h.half_life,
           h.peak_concentration,
           h.cleared_percentage,
           h.action_type
    FROM peptides p
    JOIN peptide_graph pg ON pg.peptide_id = p.id
    LEFT JOIN administration_methods am ON am.id = pg.administration_method_id
    LEFT JOIN headline h ON h.peptide_id = p.id
    GROUP BY p.id, p.name, p.slug, h.method, h.half_life,
             h.peak_concentration, h.cleared_percentage, h.action_type
    ORDER BY p.name
"""


def pk_summary_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Shape one PK_SUMMARY_SQL row for the API (pure, unit-tested)."""
    slug = (row.get("slug") or "").strip() or None
    last = row.get("last_updated")
    methods = sorted(m for m in (row.get("methods") or []) if m)
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": slug,
        "source": "pep-pedia.org",
        "source_url": PEP_PEDIA_PEPTIDE_URL.format(slug=slug) if slug else None,
        "methods": methods,
        "curve_count": int(row.get("curve_count") or 0),
        "last_updated": last.isoformat() if hasattr(last, "isoformat") else last,
        "action_type": row.get("action_type"),
        "headline": {
            "method": row.get("headline_method"),
            "half_life": row.get("half_life") or None,
            "peak": row.get("peak_concentration") or None,
            "cleared": row.get("cleared_percentage") or None,
        },
    }


class GraphRepository(BaseRepository):
    """Repository for peptide graph data (pharmacokinetics) operations."""

    def upsert(self, peptide_id: int, am_id: int, graph_data: Dict[str, Any], action_type: str = 'manual'):
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
                set_clause += ", action_type = %s, updated_at = NOW()"
                params = list(fields.values()) + [action_type, graph_id]
                cur.execute(f"UPDATE peptide_graph SET {set_clause} WHERE id = %s", params)
                self._commit()
                self.log_operation("UPDATE_GRAPH", "peptide_graph", 
                    f"Peptide {peptide_id}: '{graph_data['time_range']}'")
            else:
                cols = ["peptide_id", "administration_method_id", "time_range", "action_type"] + list(fields.keys())
                vals = [peptide_id, am_id, graph_data['time_range'], action_type] + list(fields.values())
                graph_id = self._insert_guarded(cur, "peptide_graph", cols, vals)
                self._commit()
                self.log_operation("INSERT_GRAPH", "peptide_graph", 
                    f"Peptide {peptide_id}: '{graph_data['time_range']}' (ID: {graph_id})")

    def list_peptides_with_graph(self) -> List[Dict[str, Any]]:
        """Peptides with at least one ``peptide_graph`` row, as ``{id, name}``, by name."""
        peptides = self.execute_all("""
            SELECT DISTINCT p.id, p.name
            FROM peptides p
            JOIN peptide_graph pg ON p.id = pg.peptide_id
            ORDER BY p.name
        """)
        return [{"id": row["id"], "name": row["name"]} for row in peptides]

    def list_pk_summary(self) -> List[Dict[str, Any]]:
        """Every peptide with PK curves, with its source and last-written time."""
        return [pk_summary_row_to_dict(row) for row in self.execute_all(PK_SUMMARY_SQL)]

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
