import json
from typing import Any, Dict, List
from src.mappers.base import BaseMapper


class GraphMapper(BaseMapper):
    """Group D: Maps pharmacokinetics graph data for DB insertion.

    Handles two input formats:
    1. src pipeline format (via csv_storage.py -> dataclasses.asdict()):
       {
         "24h": {
           "peak": "48 min", "half_life": "8 hrs", "cleared": "~1.7 days",
           "path_data": "M 10 35 C ...",
           "points": [{"x": 10.0, "y": 35.0}, ...],
           "markers": [{"cx": 41.82, "cy": 20.60, "r": 0.7, "fill": "#f59e0b"}, ...],
           "legend": {"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"},
           "x_axis_labels": [{"pos": 10.0, "label": "Dose"}, ...],
           "y_axis_labels": [{"pos": 8.0, "label": "100%"}, ...]
         }
       }
    2. graph/scraper.py JSON format:
       {
         "24h": {
           "metadata": {"peak": "48 min", "half_life": "8 hrs", "cleared": "~1.7 days"},
           "legend": {"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"},
           "path_data": "M 10 35 C ...",
           "points": [{"x": 10.0, "y": 35.0}, ...],
           "markers": [{"cx": 41.82, "cy": 20.60, "r": 0.7, "fill": "#f59e0b"}, ...],
           "x_labels": [{"pos": 10.0, "text": "Dose"}, ...],   <- note: "text" key
           "y_labels": [{"pos": 8.0, "text": "100%"}, ...]
         }
       }

    DB columns: time_range, peak_concentration, half_life, cleared_percentage,
                path_data (TEXT), markers (JSONB), points (JSONB),
                x_axis_labels (JSONB), y_axis_labels (JSONB), legend (JSONB)
    """

    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        graph_data_list = []
        graph_data_json = row.get("graph_data_json", "")

        if not graph_data_json:
            return graph_data_list
            
        try:
            # Deserialize the JSON string (stored in CSV column)
            data = json.loads(graph_data_json)

            method = row.get("Method", "Injectable")
            for time_range, details in data.items():
                # --- Peak / Half-life / Cleared ---
                # Format 2 (graph/scraper.py) nests these under "metadata"
                # Format 1 (src pipeline via asdict) puts them at root level
                metadata = details.get("metadata", {})
                peak = metadata.get("peak") or details.get("peak", "")
                half_life = metadata.get("half_life") or details.get("half_life", "")
                cleared = metadata.get("cleared") or details.get("cleared", "")

                # --- Path Data (raw SVG d attribute) ---
                path_data = details.get("path_data") or ""

                # --- Points (parsed SVG coordinates) ---
                # Both formats produce [{"x": ..., "y": ...}]
                points = details.get("points", [])

                # --- Markers (circle elements: cx, cy, r, fill) ---
                # Both formats produce [{"cx": ..., "cy": ..., "r": ..., "fill": ...}]
                markers = details.get("markers", [])

                # --- Axis Labels ---
                # Format 1 (src/asdict): key="x_axis_labels", label key="label"
                # Format 2 (graph/scraper.py): key="x_labels", label key="text"
                x_labels_raw = details.get("x_axis_labels") or details.get("x_labels", [])
                y_labels_raw = details.get("y_axis_labels") or details.get("y_labels", [])

                # Normalize label key: graph/scraper.py uses "text", src uses "label"
                x_labels = self._normalize_labels(x_labels_raw)
                y_labels = self._normalize_labels(y_labels_raw)

                # --- Legend (marker type to color mapping) ---
                legend = details.get("legend", {})

                graph_data_list.append({
                    "time_range": time_range,
                    "method": method,
                    "peak_concentration": peak,
                    "half_life": half_life,
                    "cleared_percentage": cleared,
                    "path_data": path_data,
                    "markers": json.dumps(markers),
                    "points": json.dumps(points),
                    "x_axis_labels": json.dumps(x_labels),
                    "y_axis_labels": json.dumps(y_labels),
                    "legend": json.dumps(legend),
                })
        except Exception as e:
            print(f"[WARNING] Failed to parse graph_data_json: {e}")

        return graph_data_list

    def _normalize_labels(self, labels: List[Dict]) -> List[Dict]:
        """Normalize axis label dicts to a consistent {pos, label} format.

        graph/scraper.py uses "text" as the label key.
        src/extractors/graph.py (via AxisLabel dataclass) uses "label".
        We standardize to "label" for DB storage.
        """
        normalized = []
        for item in labels:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "pos": item.get("pos", 0),
                "label": item.get("label") or item.get("text", ""),
            })
        return normalized
