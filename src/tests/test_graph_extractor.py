import pytest
from unittest.mock import MagicMock
from src.extractors.graph import GraphExtractor
from src.core.models import GraphPoint, AxisLabel


# -----------------------------------------------------------------------
# _parse_path_data
# -----------------------------------------------------------------------

def test_parse_path_data_cubic_bezier():
    """Original cubic-bezier (C) path still works."""
    extractor = GraphExtractor()
    d = "M 10 35 C 10.258 35, 10.344 18.939448089763758, 10.86 10.64 C 11.376 2.3405519102362433, 11.204 7.857189823324366, 11.72 7.33517303412081"

    points = extractor._parse_path_data(d)

    assert len(points) == 3
    assert points[0] == GraphPoint(x=10.0, y=35.0)
    assert points[1].x == 10.86
    assert points[1].y == 10.64
    assert points[2].x == 11.72
    assert points[2].y == 7.33517303412081


def test_parse_path_data_line_to():
    """L (line-to) commands: only 2 coords, last pair = endpoint."""
    extractor = GraphExtractor()
    d = "M 0 100 L 50 80 L 100 60"

    points = extractor._parse_path_data(d)

    assert len(points) == 3
    assert points[0] == GraphPoint(x=0.0, y=100.0)
    assert points[1] == GraphPoint(x=50.0, y=80.0)
    assert points[2] == GraphPoint(x=100.0, y=60.0)


def test_parse_path_data_quadratic_bezier():
    """Q (quadratic bezier) commands: 4 coords, last pair = endpoint."""
    extractor = GraphExtractor()
    d = "M 0 10 Q 25 0 50 10 Q 75 20 100 10"

    points = extractor._parse_path_data(d)

    assert len(points) == 3
    assert points[0] == GraphPoint(x=0.0, y=10.0)
    assert points[1] == GraphPoint(x=50.0, y=10.0)
    assert points[2] == GraphPoint(x=100.0, y=10.0)


def test_parse_path_data_mixed_commands():
    """Mixed M, L, C commands in one path."""
    extractor = GraphExtractor()
    d = "M 0 0 L 10 20 C 15 30, 20 40, 30 50"

    points = extractor._parse_path_data(d)

    assert len(points) == 3
    assert points[0] == GraphPoint(x=0.0, y=0.0)
    assert points[1] == GraphPoint(x=10.0, y=20.0)
    assert points[2] == GraphPoint(x=30.0, y=50.0)


def test_parse_path_data_empty():
    """Empty path returns empty list."""
    extractor = GraphExtractor()
    assert extractor._parse_path_data("") == []


# -----------------------------------------------------------------------
# _has_graph
# -----------------------------------------------------------------------

def test_has_graph_returns_false_when_no_elements():
    """_has_graph should return False when driver finds no matching container."""
    extractor = GraphExtractor()
    mock_driver = MagicMock()
    mock_driver.find_elements.return_value = []
    assert extractor._has_graph(mock_driver) is False


def test_has_graph_returns_true_when_elements_found():
    """_has_graph should return True when at least one container is found."""
    extractor = GraphExtractor()
    mock_driver = MagicMock()
    mock_driver.find_elements.return_value = [MagicMock()]
    assert extractor._has_graph(mock_driver) is True


# -----------------------------------------------------------------------
# _scrape_current_view (mock)
# -----------------------------------------------------------------------

def test_scrape_current_view_mock():
    extractor = GraphExtractor()
    mock_container = MagicMock()

    # Mock summary buttons
    mock_btn1 = MagicMock()
    mock_btn1.text = "Peak: 2 hrs"
    mock_container.find_elements.side_effect = lambda by, selector: [mock_btn1] if "flex.items-center.gap-4" in selector else []

    # Mock SVG
    mock_svg = MagicMock()
    mock_container.find_element.side_effect = lambda by, tag: mock_svg if tag == "svg" else MagicMock()

    mock_path = MagicMock()
    mock_path.get_attribute.return_value = "M 10 35"
    mock_svg.find_element.return_value = mock_path

    # Mock labels
    mock_label = MagicMock()
    mock_label.get_attribute.return_value = "10"
    mock_label.text = "Dose"
    mock_svg.find_elements.return_value = [mock_label]

    data = extractor._scrape_current_view(mock_container, "24h")

    assert data.peak == "2 hrs"
    assert len(data.points) == 1
    assert data.points[0].x == 10.0
    assert len(data.x_axis_labels) == 1
    assert data.x_axis_labels[0].label == "Dose"

