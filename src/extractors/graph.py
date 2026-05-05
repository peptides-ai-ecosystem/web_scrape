from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re
from .base import BaseExtractor
from ..core.models import GraphData, GraphPoint, AxisLabel
from ..config import TIME_RANGES
from typing import Dict, List, Optional


class GraphExtractor(BaseExtractor):
    """Extracts pharmacokinetics graph data for the currently active delivery method."""

    def extract(self, driver, wait) -> Dict[str, GraphData]:
        all_graph_data = {}

        # Guard: skip if graph section doesn't exist for this method
        if not self._has_graph(driver):
            return all_graph_data

        try:
            graph_container = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//div[contains(@class, 'rounded-xl') and .//span[contains(text(), 'Peak:')]]"
            )))

            # Wait for the initial SVG path to be ready before doing anything
            self._wait_for_graph_ready(graph_container, wait)

            # Find time-range buttons within the graph container
            time_buttons = graph_container.find_elements(
                By.CSS_SELECTOR, "div.rounded-full button"
            )

            for btn in time_buttons:
                btn_text = btn.text.strip()
                if btn_text not in TIME_RANGES:
                    continue

                self.safe_click(driver, wait, btn)
                # Wait for graph to re-render after time-range switch
                self._wait_for_graph_ready(graph_container, wait)

                data = self._scrape_current_view(graph_container, btn_text)
                if data:
                    all_graph_data[btn_text] = data

        except TimeoutException:
            print("[WARNING] Graph container not found within timeout.")
        except Exception as e:
            print(f"[WARNING] Graph extraction failed: {e}")

        return all_graph_data

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _has_graph(self, driver) -> bool:
        """Return True if a graph section exists in the current DOM."""
        return bool(driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'rounded-xl') and .//span[contains(text(), 'Peak:')]]"
        ))

    # ------------------------------------------------------------------
    # Wait helpers
    # ------------------------------------------------------------------

    def _wait_for_graph_ready(self, container, wait):
        """Wait until the SVG path data is present and non-trivial (graph rendered)."""
        def _svg_path_loaded(driver):
            try:
                path = container.find_element(
                    By.CSS_SELECTOR, "path[stroke='#3b82f6']"
                )
                d = path.get_attribute("d")
                return bool(d and len(d) > 10)
            except Exception:
                return False

        try:
            wait.until(_svg_path_loaded)
        except TimeoutException:
            # If it never loads, continue — _scrape_current_view will handle the error
            pass

    # ------------------------------------------------------------------
    # Scraping
    # ------------------------------------------------------------------

    def _scrape_current_view(self, container, time_range: str) -> Optional[GraphData]:
        try:
            peak, half_life, cleared = self._extract_summary_stats(container)
            points = self._extract_svg_points(container)
            x_labels = self._extract_x_labels(container)
            y_labels = self._extract_y_labels(container)

            return GraphData(
                peak=peak,
                half_life=half_life,
                cleared=cleared,
                points=points,
                x_axis_labels=x_labels,
                y_axis_labels=y_labels,
            )
        except Exception as e:
            print(f"[DEBUG] Graph view scraping failed for {time_range}: {e}")
            return None

    def _extract_summary_stats(self, container):
        """Extract Peak, Half-life, Cleared values robustly."""
        peak = half_life = cleared = ""

        # Strategy 1: text directly inside summary buttons
        summary_btns = container.find_elements(
            By.CSS_SELECTOR, "div.flex.items-center.gap-4 button"
        )
        for btn in summary_btns:
            text = btn.text.strip()
            if "Peak:" in text:
                peak = text.replace("Peak:", "").strip()
            elif "Half-life:" in text:
                half_life = text.replace("Half-life:", "").strip()
            elif "Cleared:" in text:
                cleared = text.replace("Cleared:", "").strip()

        # Strategy 2: label/value pairs inside <span> children
        if not peak:
            spans = container.find_elements(By.CSS_SELECTOR, "button span")
            label_map = {}
            last_label = None
            for span in spans:
                text = span.text.strip()
                if not text:
                    continue
                if text.endswith(":"):
                    last_label = text.rstrip(":")
                elif last_label:
                    label_map[last_label.lower()] = text
                    last_label = None
            peak = label_map.get("peak", peak)
            half_life = label_map.get("half-life", half_life)
            cleared = label_map.get("cleared", cleared)

        return peak, half_life, cleared

    def _extract_svg_points(self, container) -> List[GraphPoint]:
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            path = svg.find_element(By.CSS_SELECTOR, "path[stroke='#3b82f6']")
            d_attr = path.get_attribute("d")
            return self._parse_path_data(d_attr)
        except NoSuchElementException:
            return []

    def _extract_x_labels(self, container) -> List[AxisLabel]:
        labels = []
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            for elem in svg.find_elements(By.CSS_SELECTOR, "text[y='43']"):
                try:
                    labels.append(AxisLabel(
                        pos=float(elem.get_attribute("x")),
                        label=elem.text.strip()
                    ))
                except Exception:
                    continue
        except NoSuchElementException:
            pass
        return labels

    def _extract_y_labels(self, container) -> List[AxisLabel]:
        labels = []
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            for elem in svg.find_elements(By.CSS_SELECTOR, "text[text-anchor='end']"):
                try:
                    labels.append(AxisLabel(
                        pos=float(elem.get_attribute("y")),
                        label=elem.text.strip()
                    ))
                except Exception:
                    continue
        except NoSuchElementException:
            pass
        return labels

    # ------------------------------------------------------------------
    # SVG Path Parser
    # ------------------------------------------------------------------

    def _parse_path_data(self, d: str) -> List[GraphPoint]:
        """
        Parse SVG path data collecting end-points for M, L, C, Q commands.

        - M x y         → move-to (counts as a point)
        - L x y         → line-to (2 coords, last pair = endpoint)
        - C x1 y1 x2 y2 x y → cubic bezier (6 coords, last pair = endpoint)
        - Q x1 y1 x y   → quadratic bezier (4 coords, last pair = endpoint)
        """
        COORDS_PER_CMD = {"M": 2, "L": 2, "C": 6, "Q": 4}
        points: List[GraphPoint] = []

        # Tokenise: split path into command letters and number strings
        tokens = re.findall(r"[MLCQZmlcqz]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)

        current_cmd: Optional[str] = None
        num_buf: List[float] = []

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
                    points.append(GraphPoint(x=num_buf[-2], y=num_buf[-1]))
                    num_buf = []  # reset for repeated commands (e.g. implicit L)

        return points
