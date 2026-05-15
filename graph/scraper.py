import os
import sys
import json
import time
import re
from typing import Dict, List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add the project root to sys.path to allow imports from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.webdriver_factory import WebDriverFactory
from src.config import TIME_RANGES

def parse_svg_path(d: str) -> List[Dict[str, float]]:
    """Parse SVG path data into a list of (x, y) points."""
    COORDS_PER_CMD = {"M": 2, "L": 2, "C": 6, "Q": 4}
    points = []
    tokens = re.findall(r"[MLCQZmlcqz]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    current_cmd = None
    num_buf = []

    for token in tokens:
        upper = token.upper()
        if upper in COORDS_PER_CMD:
            current_cmd = upper
            num_buf = []
        elif upper == "Z":
            current_cmd = None
            num_buf = []
        else:
            try:
                num_buf.append(float(token))
            except ValueError:
                continue
            if current_cmd and len(num_buf) == COORDS_PER_CMD[current_cmd]:
                points.append({"x": num_buf[-2], "y": num_buf[-1]})
                num_buf = [] 
    return points

def extract_summary_stats(container):
    peak = half_life = cleared = ""
    summary_btns = container.find_elements(By.CSS_SELECTOR, "div.flex.items-center.gap-4 button")
    for btn in summary_btns:
        text = btn.text.strip().replace("\n", " ")
        if "Peak:" in text:
            peak = text.split("Peak:")[1].strip()
        elif "Half-life:" in text:
            half_life = text.split("Half-life:")[1].strip()
        elif "Cleared:" in text:
            cleared = text.split("Cleared:")[1].strip()
    return peak, half_life, cleared

def extract_markers(container):
    markers = []
    try:
        svg = container.find_element(By.TAG_NAME, "svg")
        circles = svg.find_elements(By.TAG_NAME, "circle")
        for circle in circles:
            markers.append({
                "cx": float(circle.get_attribute("cx")),
                "cy": float(circle.get_attribute("cy")),
                "r": float(circle.get_attribute("r")),
                "fill": circle.get_attribute("fill")
            })
    except Exception:
        pass
    return markers

def extract_labels(container):
    x_labels = []
    y_labels = []
    try:
        svg = container.find_element(By.TAG_NAME, "svg")
        # X-axis labels are usually at y=43
        for elem in svg.find_elements(By.CSS_SELECTOR, "text[y='43']"):
            x_labels.append({"pos": float(elem.get_attribute("x")), "text": elem.text.strip()})
        # Y-axis labels are usually text-anchor="end"
        for elem in svg.find_elements(By.CSS_SELECTOR, "text[text-anchor='end']"):
            y_labels.append({"pos": float(elem.get_attribute("y")), "text": elem.text.strip()})
    except Exception:
        pass
    return x_labels, y_labels

def wait_for_graph_update(container, wait, old_d=None, timeout=5):
    """Wait for the graph SVG to change from old_d."""
    def _graph_updated(driver):
        try:
            path = container.find_element(By.CSS_SELECTOR, "path[stroke='#3b82f6']")
            new_d = path.get_attribute("d")
            if not new_d or len(new_d) < 10:
                return False
            return new_d != old_d
        except Exception:
            return False
    
    try:
        wait.until(_graph_updated)
    except TimeoutException:
        pass

def extract_legend(driver, container):
    """Extract which color corresponds to which marker type from the legend."""
    legend = {}
    try:
        # The legend is usually at the bottom: Peak, Half-life
        legend_container = container.find_element(By.CSS_SELECTOR, "div.border-t")
        items = legend_container.find_elements(By.TAG_NAME, "button")
        for item in items:
            label = item.text.strip()
            # The color is in a child div
            dot = item.find_element(By.CSS_SELECTOR, "div.rounded-full")
            # Check the actual computed background-color
            color = driver.execute_script("return window.getComputedStyle(arguments[0]).backgroundColor;", dot)
            # Convert rgb(r, g, b) to hex if possible or just store as is
            legend[label.lower()] = color
    except Exception:
        # Fallback to defaults if legend extraction fails
        pass
    return legend

def scrape_graph(url: str):
    driver, wait = WebDriverFactory.create_driver()
    all_data = {}

    try:
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Look for the graph container
        graph_xpath = "//div[contains(@class, 'rounded-xl') and .//span[contains(text(), 'Peak:')]]"
        container = wait.until(EC.presence_of_element_located((By.XPATH, graph_xpath)))
        print("Graph container found.")

        # Find tabs
        time_buttons = container.find_elements(By.CSS_SELECTOR, "div.rounded-full button")
        
        current_d = None
        
        for btn in time_buttons:
            label = btn.text.strip()
            if label not in TIME_RANGES:
                continue
            
            print(f"Scraping tab: {label}")
            driver.execute_script("arguments[0].click();", btn)
            
            # Wait for graph update
            wait_for_graph_update(container, wait, old_d=current_d)
            time.sleep(0.5) # Extra buffer for final positioning

            # Extract data
            peak, hl, cl = extract_summary_stats(container)
            legend = extract_legend(driver, container)
            
            # Extract main path
            path_elem = container.find_element(By.CSS_SELECTOR, "path[stroke='#3b82f6']")
            current_d = path_elem.get_attribute("d")
            points = parse_svg_path(current_d)
            
            # Extract markers
            markers = extract_markers(container)
            
            # Extract labels
            x_labels, y_labels = extract_labels(container)

            all_data[label] = {
                "metadata": {"peak": peak, "half_life": hl, "cleared": cl},
                "legend": legend,
                "path_data": current_d,
                "points": points,
                "markers": markers,
                "x_labels": x_labels,
                "y_labels": y_labels
            }

        with open("graph/graph_data.json", "w") as f:
            json.dump(all_data, f, indent=2)
        print("Data saved to graph/graph_data.json")

    except Exception as e:
        print(f"Extraction failed: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://pep-pedia.org/peptides/dihexa"
    scrape_graph(target_url)
