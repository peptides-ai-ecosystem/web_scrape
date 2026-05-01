from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import re
from .base import BaseExtractor
from ..core.models import GraphData, GraphPoint, AxisLabel
from typing import Dict

class GraphExtractor(BaseExtractor):
    def extract(self, driver, wait) -> Dict[str, GraphData]:
        all_graph_data = {}
        try:
            # Find the graph container using a more robust XPATH
            # It's a div that contains a span with "Peak:"
            graph_container = wait.until(EC.presence_of_element_located((
                By.XPATH, "//div[contains(@class, 'rounded-xl') and .//span[contains(text(), 'Peak:')]]"
            )))
            
            # Find time range buttons - they are in a div with rounded-full
            time_buttons = graph_container.find_elements(By.CSS_SELECTOR, "div.rounded-full button")
            
            # Core time ranges to extract
            ranges = ["24h", "7d", "14d", "30d"]
            
            for btn in time_buttons:
                btn_text = btn.text.strip()
                if btn_text in ranges:
                    self.safe_click(driver, wait, btn)
                    self.wait_for_loading(0.8) # Wait for graph animation/update
                    
                    data = self._scrape_current_view(graph_container)
                    if data:
                        all_graph_data[btn_text] = data
        except Exception as e:
            print(f"[WARNING] Graph extraction failed: {e}")
            
        return all_graph_data

    def _scrape_current_view(self, container) -> GraphData:
        try:
            # Summary values
            peak = ""
            half_life = ""
            cleared = ""
            
            summary_btns = container.find_elements(By.CSS_SELECTOR, "div.flex.items-center.gap-4 button")
            for btn in summary_btns:
                text = btn.text.strip()
                if "Peak:" in text:
                    peak = text.replace("Peak:", "").strip()
                elif "Half-life:" in text:
                    half_life = text.replace("Half-life:", "").strip()
                elif "Cleared:" in text:
                    cleared = text.replace("Cleared:", "").strip()

            # If text is not directly in button (sometimes it is in spans)
            if not peak:
                spans = container.find_elements(By.CSS_SELECTOR, "button span")
                for i in range(len(spans)-1):
                    label = spans[i].text.strip()
                    value = spans[i+1].text.strip()
                    if "Peak:" in label: peak = value
                    elif "Half-life:" in label: half_life = value
                    elif "Cleared:" in label: cleared = value

            # SVG Data
            svg = container.find_element(By.TAG_NAME, "svg")
            path = svg.find_element(By.CSS_SELECTOR, "path[stroke='#3b82f6']")
            d_attr = path.get_attribute("d")
            
            points = self._parse_path_data(d_attr)
            
            # X Axis Labels
            x_labels = []
            x_text_elems = svg.find_elements(By.CSS_SELECTOR, "text[y='43']")
            for elem in x_text_elems:
                try:
                    x_pos = float(elem.get_attribute("x"))
                    label = elem.text.strip()
                    x_labels.append(AxisLabel(pos=x_pos, label=label))
                except: continue

            # Y Axis Labels
            y_labels = []
            y_text_elems = svg.find_elements(By.CSS_SELECTOR, "text[text-anchor='end']")
            for elem in y_text_elems:
                try:
                    y_pos = float(elem.get_attribute("y"))
                    label = elem.text.strip()
                    y_labels.append(AxisLabel(pos=y_pos, label=label))
                except: continue

            return GraphData(
                peak=peak,
                half_life=half_life,
                cleared=cleared,
                points=points,
                x_axis_labels=x_labels,
                y_axis_labels=y_labels
            )
        except Exception as e:
            print(f"[DEBUG] View scraping failed: {e}")
            return None

    def _parse_path_data(self, d):
        # Very basic parser for SVG path with M and C/L commands
        # Example: M 10 35 C 10.258 35, 10.344 18.939, 10.86 10.64
        points = []
        # Find all numbers
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", d)
        float_nums = [float(n) for n in nums]
        
        # In this specific graph path:
        # M x1 y1
        # C x2 y2, x3 y3, x4 y4
        # We want the 'end' points of each command if it's a curve, 
        # or simplified points to represent the shape.
        # For simplicity, let's just take every pair of coordinates as a potential point
        # even if some are control points for Bezier. 
        # The true "data points" are usually the last pair in each C command.
        
        # Actually, let's just take the first M and then the last pair of each C command
        if len(float_nums) >= 2:
            points.append(GraphPoint(x=float_nums[0], y=float_nums[1]))
            
            # Skip M (2 nums)
            curr = 2
            while curr + 5 < len(float_nums):
                # Curve has 6 numbers (3 pairs)
                # target point is the last pair
                points.append(GraphPoint(x=float_nums[curr+4], y=float_nums[curr+5]))
                curr += 6
                
        return points
