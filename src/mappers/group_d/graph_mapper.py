import json
from typing import Any, Dict, List
from src.mappers.base import BaseMapper

class GraphMapper(BaseMapper):
    """Group D: Maps pharmacokinetics graph data."""
    
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        graph_data_list = []
        graph_data_json = row.get("graph_data_json", "")
        
        if not graph_data_json:
            return graph_data_list
            
        try:
            # The CSV stores graph_data_json as a JSON string containing a dict keyed by time range
            # { "24h": { "peak": "...", "points": [...], ... }, "7d": ... }
            data = json.loads(graph_data_json)
            
            for time_range, details in data.items():
                graph_data_list.append({
                    "time_range": time_range,
                    "peak_concentration": details.get("peak"),
                    "half_life": details.get("half_life"),
                    "cleared_percentage": details.get("cleared"),
                    "points": json.dumps(details.get("points", [])),
                    "x_axis_labels": json.dumps(details.get("x_axis_labels", [])),
                    "y_axis_labels": json.dumps(details.get("y_axis_labels", [])),
                })
        except Exception as e:
            print(f"[WARNING] Failed to parse graph_data_json: {e}")
            
        return graph_data_list
