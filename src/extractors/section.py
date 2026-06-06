from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.extractors.base import BaseExtractor
from typing import List, Dict
from src.config import BUTTON_SKIP_LIST as button_skip_list


class SectionExtractor(BaseExtractor):
    def extract(self, driver, wait) -> List[Dict[str, str]]:
        data = []
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.mb-12")))
            sections = driver.find_elements(By.CSS_SELECTOR, "section.mb-12")
            
            for section in sections:
                h2_text = self._get_h2_heading(section)
                section_data = {}
                
                if self._has_accordions(section):
                    self._process_accordions(section, h2_text, section_data, driver, wait)
                elif self._has_tabs(section):
                    self._process_tabs(section, h2_text, section_data, driver, wait)
                elif self._has_table(section):
                    self._process_table(section, h2_text, section_data)
                elif self._has_numbered_steps(section):
                    self._process_numbered_steps(section, h2_text, section_data)
                elif self._has_checkmark_list(section):
                    self._process_checkmark_list(section, h2_text, section_data)
                elif self._has_bullet_list(section):
                    self._process_bullet_list(section, h2_text, section_data)
                else:
                    self._process_static_content(section, h2_text, section_data)
                
                if section_data:
                    data.append(section_data)
        except TimeoutException:
            pass
        return data

    def _get_h2_heading(self, section):
        h2_elements = section.find_elements(By.XPATH, ".//h2")
        if h2_elements:
            text = h2_elements[0].text.strip()
            return text.lower().replace(" ", "_").replace("&", "and")
        return "unknown"

    def _has_tabs(self, section):
        return bool(section.find_elements(By.CSS_SELECTOR, "div.rounded-xl div.border-b div.flex.gap-6 > button"))

    def _has_accordions(self, section):
        return bool(section.find_elements(By.CSS_SELECTOR, "button[data-state]"))

    def _has_table(self, section):
        return bool(section.find_elements(By.TAG_NAME, "table"))

    def _has_numbered_steps(self, section):
        steps = section.find_elements(By.XPATH, ".//div[contains(@class, 'rounded-full')]")
        if steps:
            first_text = steps[0].text.strip()
            return first_text.isdigit()
        return False

    def _has_checkmark_list(self, section):
        items = section.find_elements(By.XPATH, ".//div[contains(@class, 'rounded-full')]")
        if items:
            first_text = items[0].text.strip()
            return first_text in ["✓", "!", "✗"]
        return False

    def _has_bullet_list(self, section):
        return bool(section.find_elements(By.XPATH, ".//li"))

    def _process_tabs(self, section, h2_text, section_data, driver, wait):
        tab_buttons = section.find_elements(By.XPATH, ".//div[contains(@class, 'border-b')]//button")
        if not tab_buttons: return

        for tab_btn in tab_buttons:
            try:
                tab_name = tab_btn.find_element(By.CSS_SELECTOR, "span.font-medium").text.strip().lower().replace(" ", "_").replace("&", "and")
                self.safe_click(driver, wait, tab_btn)
                wait.until(lambda d: "border" in tab_btn.get_attribute("class"))
                tab_parent = tab_btn.find_element(By.XPATH, "./ancestor::div[contains(@class, 'border-b')]")
                content_area = tab_parent.find_element(By.XPATH, "./following-sibling::div[1]")

                buttons = content_area.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "show" in btn.text.lower() and "more" in btn.text.lower():
                        try:
                            self.safe_click(driver, wait, btn)
                            self.wait_for_loading(0.5)
                            content_area = tab_parent.find_element(By.XPATH, "./following-sibling::div[1]")
                        except Exception:
                            pass

                h4_elements = content_area.find_elements(By.TAG_NAME, "h4")
                citation_cards = content_area.find_elements(By.CSS_SELECTOR, "div.p-6 > p")

                if h4_elements:
                    for h4 in h4_elements:
                        parent_div = h4.find_element(By.XPATH, "./parent::div")
                        content_parts = []
                        elems = parent_div.find_elements(By.XPATH, "./*[self::div or self::p or self::a]")
                        for elem in elems:
                            text = elem.text.strip()
                            if text and text not in content_parts:
                                content_parts.append(text)
                        column_name = f"{h2_text}_{tab_name}_({h4.text.strip().replace('-', '').replace(' ', '_')})"
                        section_data[column_name] = " ".join(content_parts)
                elif citation_cards and tab_name == "citations":
                    cards = content_area.find_elements(By.CSS_SELECTOR, "div.p-6")
                    for idx, card in enumerate(cards, 1):
                        content_parts = []
                        for elem in card.find_elements(By.XPATH, ".//*"):
                            text = elem.text.strip()
                            if text and text not in content_parts:
                                content_parts.append(text)
                                if elem.tag_name == "a":
                                    href = elem.get_attribute("href")
                                    if href and href not in content_parts:
                                        content_parts.append(href)
                        column_name = f"{h2_text}_{tab_name}_{idx}"
                        section_data[column_name] = " ".join(content_parts)
                else:
                    list_items = content_area.find_elements(By.XPATH, ".//li")
                    if list_items:
                        for idx, li in enumerate(list_items, 1):
                            column_name = f"{h2_text}_{tab_name}_{idx}"
                            section_data[column_name] = li.text.strip()
                    else:
                        column_name = f"{h2_text}_{tab_name}"
                        section_data[column_name] = content_area.text.strip()
            except Exception:
                continue

    def _process_accordions(self, section, h2_text, section_data, driver, wait):
        accordion_buttons = section.find_elements(By.CSS_SELECTOR, "button[data-state]")
        for btn in accordion_buttons:
            try:
                btn_text = btn.text.strip().lower()
                if any(skip in btn_text for skip in button_skip_list):
                    continue
                title = btn.text.strip().lower().replace(" ", "_").replace("/", "_").replace("\n", "_")
                if btn.get_attribute("data-state") == "closed":
                    self.safe_click(driver, wait, btn)
                    self.wait_for_loading(0.5)
                panel_id = btn.get_attribute("aria-controls")
                panel = section.find_element(By.ID, panel_id)
                h4_elements = panel.find_elements(By.TAG_NAME, "h4")
                if h4_elements:
                    for h4 in h4_elements:
                        h4_text = h4.text.strip().lower().replace(" ", "_").replace("/", "_")
                        try:
                            content = h4.find_element(By.XPATH, "./following-sibling::p").text.strip()
                        except:
                            content = h4.find_element(By.XPATH, "./parent::div").text.strip()
                        column_name = f"{h2_text}_{title}_({h4_text})"
                        section_data[column_name] = content
                else:
                    content_text = panel.text.strip()
                    if title in content_text.lower():
                        p_elements = panel.find_elements(By.TAG_NAME, "p")
                        if p_elements:
                            content_text = " ".join([p.text.strip() for p in p_elements])
                    column_name = f"{h2_text}_{title}"
                    section_data[column_name] = content_text
            except Exception:
                continue

    def _process_table(self, section, h2_text, section_data):
        disclaimer = section.find_elements(By.XPATH, ".//div[contains(@class, 'amber-50')]//p")
        if disclaimer:
            section_data[f"{h2_text}_info"] = disclaimer[0].text.strip()
        table = section.find_element(By.TAG_NAME, "table")
        headers = [th.text.strip().lower().replace(" ", "_") for th in table.find_elements(By.TAG_NAME, "th")]
        rows = table.find_elements(By.TAG_NAME, "tbody")[0].find_elements(By.TAG_NAME, "tr")
        for row_idx, row in enumerate(rows, 1):
            cells = row.find_elements(By.TAG_NAME, "td")
            for col_idx, cell in enumerate(cells):
                if col_idx < len(headers):
                    column_name = f"{h2_text}_{headers[col_idx]}_{row_idx}"
                    section_data[column_name] = cell.text.strip()
        timing_note = section.find_elements(By.XPATH, ".//div[contains(@class, 'blue-50')]//p")
        if timing_note:
            section_data[f"{h2_text}_timing"] = timing_note[0].text.strip()

    def _process_numbered_steps(self, section, h2_text, section_data):
        disclaimer = section.find_elements(By.XPATH, ".//div[contains(@class, 'amber-50')]//p")
        if disclaimer:
            section_data[f"{h2_text}_info"] = disclaimer[0].text.strip()
        step_containers = section.find_elements(By.XPATH, ".//div[contains(@class, 'flex gap-4 items-start')]")
        for container in step_containers:
            try:
                step_num = container.find_element(By.XPATH, ".//div[contains(@class, 'rounded-full')]").text.strip()
                content = container.find_element(By.TAG_NAME, "p").text.strip()
                section_data[f"{h2_text}_{step_num}"] = content
            except:
                continue

    def _process_checkmark_list(self, section, h2_text, section_data):
        list_containers = section.find_elements(By.XPATH, ".//div[contains(@class, 'flex gap-4 items-start')]")
        for container in list_containers:
            try:
                icon = container.find_element(By.XPATH, ".//div[contains(@class, 'rounded-full')]").text.strip()
                content_div = container.find_element(By.XPATH, ".//div[not(contains(@class, 'rounded-full'))]")
                h3_text = content_div.find_element(By.TAG_NAME, "h3").text.strip()
                content = content_div.find_element(By.TAG_NAME, "p").text.strip()
                section_data[f"{h2_text}_{h3_text}({icon})"] = content
            except:
                continue

    def _process_bullet_list(self, section, h2_text, section_data):
        list_items = section.find_elements(By.XPATH, ".//ul/li")
        for idx, li in enumerate(list_items, 1):
            section_data[f"{h2_text}_{idx}"] = li.text.strip()

    def _process_static_content(self, section, h2_text, section_data):
        h3_elements = section.find_elements(By.TAG_NAME, "h3")
        if h3_elements:
            for h3 in h3_elements:
                try:
                    h3_text = h3.text.strip().lower().replace(" ", "_").replace("?", "")
                    content = h3.find_element(By.XPATH, "./following-sibling::p").text.strip()
                    section_data[f"{h2_text}_{h3_text}"] = content
                except:
                    continue
        grid_divs = section.find_elements(By.XPATH, ".//div[contains(@class, 'grid')]//div/p[@class and contains(@class, 'text-xs')]")
        if grid_divs:
            for div in grid_divs:
                try:
                    label = div.text.strip().lower().replace(" ", "_")
                    value = div.find_element(By.XPATH, "./following-sibling::p").text.strip()
                    section_data[f"{h2_text}_{label}"] = value
                except:
                    continue
        code_blocks = section.find_elements(By.XPATH, ".//div/p[contains(@class, 'font-mono')]")
        if code_blocks:
            section_data[f"{h2_text}_amino_acid_sequence"] = code_blocks[0].text.strip()
        if not section_data:
            section_data[f"{h2_text}_others"] = section.text.strip()
