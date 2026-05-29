from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class HeroFact:
    label: str
    value: str
    extra: str = ""

@dataclass
class HeroData:
    name: str
    subtitle: str
    facts: List[HeroFact] = field(default_factory=list)

@dataclass
class SectionData:
    heading: str
    content: Dict[str, str] = field(default_factory=dict)

@dataclass
class GraphPoint:
    x: float
    y: float

@dataclass
class AxisLabel:
    pos: float
    label: str

@dataclass
class GraphData:
    peak: str
    half_life: str
    cleared: str
    path_data: str = ""
    points: List[GraphPoint] = field(default_factory=list)
    markers: List[Dict] = field(default_factory=list)
    legend: Dict[str, str] = field(default_factory=dict)
    x_axis_labels: List[AxisLabel] = field(default_factory=list)
    y_axis_labels: List[AxisLabel] = field(default_factory=list)

@dataclass
class PeptideData:
    name: str
    full_name: str
    method: str
    url: str
    hero: HeroData
    quick_guide: Dict[str, str] = field(default_factory=dict)
    community_insights: Dict[str, str] = field(default_factory=dict)
    poll_results: Dict[str, str] = field(default_factory=dict)
    sections: List[Dict[str, str]] = field(default_factory=list)
    graph_data: Dict[str, GraphData] = field(default_factory=dict) # Keyed by time range (24h, 7d, etc.)
