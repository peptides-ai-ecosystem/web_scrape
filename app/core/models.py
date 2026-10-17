from dataclasses import dataclass, field
from enum import Enum


class ScrapeMode(Enum):
    """Controls which extractors run during a scrape.

    - FULL:       All extractors (Hero, QuickGuide, Community, Section, Graph)
    - CORE_ONLY:  Skip GraphExtractor (graph data not needed for core sync)
    - GRAPH_ONLY: Skip QuickGuide, Community, Section (only graph data needed)
    """

    FULL = "full"
    CORE_ONLY = "core"
    GRAPH_ONLY = "graph"


@dataclass
class HeroFact:
    label: str
    value: str
    extra: str = ""


@dataclass
class HeroData:
    name: str
    subtitle: str
    facts: list[HeroFact] = field(default_factory=list)
    research_level: str = "Limited Research"


@dataclass
class SectionData:
    heading: str
    content: dict[str, str] = field(default_factory=dict)


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
    points: list[GraphPoint] = field(default_factory=list)
    markers: list[dict] = field(default_factory=list)
    legend: dict[str, str] = field(default_factory=dict)
    x_axis_labels: list[AxisLabel] = field(default_factory=list)
    y_axis_labels: list[AxisLabel] = field(default_factory=list)


@dataclass
class PeptideData:
    name: str
    full_name: str
    method: str
    url: str
    hero: HeroData
    quick_guide: dict[str, str] = field(default_factory=dict)
    community_insights: dict[str, str] = field(default_factory=dict)
    poll_results: dict[str, str] = field(default_factory=dict)
    sections: list[dict[str, str]] = field(default_factory=list)
    graph_data: dict[str, GraphData] = field(default_factory=dict)  # Keyed by time range (24h, 7d, etc.)
