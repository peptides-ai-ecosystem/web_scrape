import pytest
from unittest.mock import MagicMock
from src.extractors.graph import GraphExtractor
from src.core.models import GraphPoint, AxisLabel

def test_parse_path_data():
    extractor = GraphExtractor()
    # Sample path from user request
    d = "M 10 35 C 10.258 35, 10.344 18.939448089763758, 10.86 10.64 C 11.376 2.3405519102362433, 11.204 7.857189823324366, 11.72 7.33517303412081"
    
    points = extractor._parse_path_data(d)
    
    # M point: (10, 35)
    # 1st C point: (10.86, 10.64)
    # 2nd C point: (11.72, 7.33517303412081)
    
    assert len(points) == 3
    assert points[0] == GraphPoint(x=10.0, y=35.0)
    assert points[1].x == 10.86
    assert points[1].y == 10.64
    assert points[2].x == 11.72
    assert points[2].y == 7.33517303412081

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
    
    data = extractor._scrape_current_view(mock_container)
    
    assert data.peak == "2 hrs"
    assert len(data.points) == 1
    assert data.points[0].x == 10.0
    assert len(data.x_axis_labels) == 1
    assert data.x_axis_labels[0].label == "Dose"
