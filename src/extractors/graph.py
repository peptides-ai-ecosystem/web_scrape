from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from src.extractors.base import BaseExtractor
from src.core.models import GraphData, GraphPoint, AxisLabel
from src.config import TIME_RANGES
from typing import Dict, List, Optional
import re
import time
from src.config import log_debug, log_error
class GraphExtractor(BaseExtractor):
    """Extracts pharmacokinetics graph data for the currently active delivery method.
    
    Aligned with graph/scraper.py extraction logic:
    - Extracts path_data (raw SVG d attribute), markers (circle elements), legend (color mapping)
    - Uses wait-for-change strategy to detect tab transitions
    """

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

            # Track the current path data to detect changes between tabs
            current_d = None

            for btn in time_buttons:
                btn_text = btn.text.strip()
                if btn_text not in TIME_RANGES:
                    continue

                # Get old path data before clicking
                old_d = current_d

                try:
                    print(f"[DEBUG] Clicking tab: {btn_text}")
                    self.safe_click(driver, wait, btn)

                    # Wait for graph to actually change (not just exist)
                    self._wait_for_graph_update(graph_container, wait, old_d=old_d)
                    time.sleep(1)  # Increased from 0.5s to give more time for animation

                    data, new_d = self._scrape_current_view(driver, graph_container, btn_text)
                    if data:
                        log_debug(f"[DEBUG] Successfully extracted {btn_text}", "graph_extractor.py")
                        all_graph_data[btn_text] = data
                        current_d = new_d
                    else:
                        log_debug(f"[WARNING] No data for {btn_text}", "graph_extractor.py")
                except Exception as e:
                    log_error(f"[ERROR] Failed to scrape tab {btn_text}: {e}", "graph_extractor.py")
                    continue

        except TimeoutException:
            log_debug("[WARNING] Graph container not found within timeout.", "graph_extractor.py")
        except Exception as e:
            log_error(f"[ERROR] Graph extraction failed: {e}", "graph_extractor.py")

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
        """Wait until the SVG path data is present and non-trivial (initial graph rendered)."""
        def _svg_path_loaded(driver):
            try:
                path = container.find_element(
                    By.CSS_SELECTOR, "path[stroke='#3b82f6']"
                )
                d = path.get_attribute("d")
                is_ready = bool(d and len(d) > 10)
                if is_ready:
                    log_debug(f"[DEBUG] Graph ready with path of {len(d)} chars", "graph_extractor.py" )
                return is_ready
            except Exception as e:
                log_debug(f"[DEBUG] Graph not ready yet: {e}", "graph_extractor.py")
                return False

        try:
            wait.until(_svg_path_loaded)
        except TimeoutException:
            # If it never loads, continue — _scrape_current_view will handle the error
            log_debug("[WARNING] Graph path readiness timeout", "graph_extractor.py")
            pass

    def _wait_for_graph_update(self, container, wait, old_d=None):
        """Wait for the graph SVG path to change from old_d.

        This is the key fix: graph/scraper.py waits for the path d attribute
        to actually change, which properly detects tab transitions.
        Without this, we can capture stale data from the previous tab.
        """
        def _graph_updated(driver):
            try:
                path = container.find_element(
                    By.CSS_SELECTOR, "path[stroke='#3b82f6']"
                )
                new_d = path.get_attribute("d")
                if not new_d or len(new_d) < 10:
                    return False
                # If old_d is None (first tab), always return True after getting data
                if old_d is None:
                    return True
                # Otherwise, check if it actually changed
                return new_d != old_d
            except Exception:
                return False

        try:
            wait.until(_graph_updated)
        except TimeoutException:
            log_debug("[WARNING] Graph update wait timed out", "graph_extractor.py")
            pass

    # ------------------------------------------------------------------
    # Scraping — aligned with graph/scraper.py
    # ------------------------------------------------------------------

    def _scrape_current_view(self, driver, container, time_range: str):
        """Scrape all graph data from the current view.

        Returns (GraphData, current_path_d) tuple.
        The current_path_d is used for wait-for-change detection on next tab.
        """
        try:
            peak, half_life, cleared = self._extract_summary_stats(container)
            legend = self._extract_legend(driver, container)

            # Extract main path data (raw SVG d attribute) + parsed points
            path_data, points = self._extract_path_and_points(container)

            # Check if there's actually a graph path extracted
            if not path_data or len(path_data) < 5:
                log_debug(f"[WARNING] No valid graph path data found for {time_range}, skipping.", "graph_extractor.py")
                return None, None

            # Extract markers (circle elements in SVG)
            markers = self._extract_markers(container)

            # Extract axis labels
            x_labels = self._extract_x_labels(container)
            y_labels = self._extract_y_labels(container)

            graph_data = GraphData(
                peak=peak,
                half_life=half_life,
                cleared=cleared,
                path_data=path_data,
                points=points,
                markers=markers,
                legend=legend,
                x_axis_labels=x_labels,
                y_axis_labels=y_labels,
            )

            # Debug logging
            log_debug(f"[DEBUG] {time_range}: peak={bool(peak)}, path_data={len(path_data) if path_data else 0}B, "
                      f"markers={len(markers)}, legend={len(legend)}, labels_x={len(x_labels)}, labels_y={len(y_labels)}", "graph_extractor.py")

            return graph_data, path_data
        except Exception as e:
            log_error(f"[ERROR] Graph view scraping failed for {time_range}: {e}", "graph_extractor.py")
            import traceback
            traceback.print_exc()
            return None, None

    def _extract_summary_stats(self, container):
        """Extract Peak, Half-life, Cleared values robustly."""
        peak = half_life = cleared = ""

        # Strategy 1: text directly inside summary buttons
        summary_btns = container.find_elements(
            By.CSS_SELECTOR, "div.flex.items-center.gap-4 button"
        )
        for btn in summary_btns:
            text = btn.text.strip().replace("\n", " ")
            if "Peak:" in text:
                peak = text.split("Peak:")[1].strip()
            elif "Half-life:" in text:
                half_life = text.split("Half-life:")[1].strip()
            elif "Cleared:" in text:
                cleared = text.split("Cleared:")[1].strip()

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

    def _extract_path_and_points(self, container):
        """Extract both the raw SVG path data and parsed points.

        graph/scraper.py stores both path_data (raw d attr) and points (parsed).
        The old src code only parsed points and lost the raw string.
        """
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            path = svg.find_element(By.CSS_SELECTOR, "path[stroke='#3b82f6']")
            d_attr = path.get_attribute("d")
            if d_attr:
                points = self._parse_path_data(d_attr)
            else:
                points = []
            return d_attr or "", points
        except (NoSuchElementException, Exception):
            return "", []

    def _extract_markers(self, container) -> List[Dict]:
        """Extract circle marker elements from SVG.

        Matches graph/scraper.py extract_markers():
        Returns list of {cx, cy, r, fill} dicts.
        """
        markers = []
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            circles = svg.find_elements(By.TAG_NAME, "circle")
            for circle in circles:
                try:
                    markers.append({
                        "cx": float(circle.get_attribute("cx")),
                        "cy": float(circle.get_attribute("cy")),
                        "r": float(circle.get_attribute("r")),
                        "fill": circle.get_attribute("fill")
                    })
                except (ValueError, TypeError):
                    # Skip markers with invalid numeric attributes
                    continue
        except Exception:
            pass
        return markers

    def _extract_legend(self, driver, container) -> Dict[str, str]:
        """Extract which color corresponds to which marker type from the legend.

        Matches graph/scraper.py extract_legend():
        The legend is at the bottom in a div.border-t, containing buttons
        with colored dots and labels.
        """
        legend = {}
        try:
            legend_container = container.find_element(By.CSS_SELECTOR, "div.border-t")
            items = legend_container.find_elements(By.TAG_NAME, "button")
            for item in items:
                label = item.text.strip()
                if not label:
                    continue
                try:
                    # The color is in a child div with rounded-full class
                    dot = item.find_element(By.CSS_SELECTOR, "div.rounded-full")
                    # Get the actual computed background-color
                    color = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).backgroundColor;", dot
                    )
                    legend[label.lower()] = color
                except Exception:
                    pass
        except Exception:
            # Fallback: legend extraction is best-effort
            pass
        return legend

    def _extract_x_labels(self, container) -> List[AxisLabel]:
        labels = []
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            for elem in svg.find_elements(By.CSS_SELECTOR, "text[y='43']"):
                try:
                    x_val = float(elem.get_attribute("x"))
                    label_text = elem.text.strip()
                    if label_text:
                        labels.append(AxisLabel(pos=x_val, label=label_text))
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception:
            pass
        return labels

    def _extract_y_labels(self, container) -> List[AxisLabel]:
        labels = []
        try:
            svg = container.find_element(By.TAG_NAME, "svg")
            for elem in svg.find_elements(By.CSS_SELECTOR, "text[text-anchor='end']"):
                try:
                    y_val = float(elem.get_attribute("y"))
                    label_text = elem.text.strip()
                    if label_text:
                        labels.append(AxisLabel(pos=y_val, label=label_text))
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception:
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
