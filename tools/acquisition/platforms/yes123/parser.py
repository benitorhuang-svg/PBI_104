"""DOM parsing and cryptographic series key calculation for yes123."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional
import urllib.parse
from bs4 import BeautifulSoup

from ...shared.geocoding import standardize_taiwan_address
from ...shared.salary_parser import extract_salary_observations


def compute_series_key(request: Dict[str, Any]) -> str:
    """Generate deterministic 20-hex series key for yes123 query."""
    identity = {
        "platform": "yes123",
        "category_code": str(request.get("category_code") or "").strip(),
        "keyword": str(request.get("keyword") or "").strip(),
    }
    if not identity["category_code"] and not identity["keyword"]:
        raise ValueError("A yes123 query requires at least a category_code or keyword")
    raw = json.dumps(identity, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def extract_reported_total(soup: BeautifulSoup) -> Optional[int]:
    """Extract reported total job count from meta description or page body."""
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content"):
        content = str(meta_desc["content"])
        match = re.search(r"(?:提供|找到|共)\s*([0-9,]+)\s*(?:個|筆)?\s*(?:工作|職缺)", content)
        if match:
            return int(match.group(1).replace(",", ""))

    body_text = soup.get_text()
    match = re.search(r"(?:提供|找到|共)\s*([0-9,]+)\s*(?:個|筆)?\s*(?:工作|職缺)", body_text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def is_taiwan_location(loc_text: str) -> bool:
    """Determine whether location text belongs to Taiwan or is overseas."""
    if not loc_text or not isinstance(loc_text, str):
        return False
    overseas_keywords = [
        "海外", "美中", "美東", "美西", "美國", "加拿大", "日本", "韓國",
        "中國", "大陸", "香港", "澳門", "越南", "泰國", "菲律賓", "新加坡",
        "馬來西亞", "印尼", "柬埔寨", "緬甸", "印度", "澳洲", "紐西蘭",
        "歐洲", "英國", "德國", "法國", "中美洲", "南美洲", "墨西哥", "巴西"
    ]
    for ov in overseas_keywords:
        if ov in loc_text:
            return False
    tw_cities = [
        "台北", "臺北", "新北", "基隆", "桃園", "新竹", "苗栗",
        "台中", "臺中", "彰化", "南投", "雲林", "嘉義", "台南",
        "臺南", "高雄", "屏東", "宜蘭", "花蓮", "台東", "臺東",
        "澎湖", "金門", "連江"
    ]
    for city in tw_cities:
        if city in loc_text:
            return True
    return bool(re.search(r"(?:市|縣|區|鄉|鎮)", loc_text))


def parse_job_cards(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Parse .Job_opening_item cards into structured records."""
    items = soup.select(".Job_opening_item")
    parsed: List[Dict[str, Any]] = []

    for item in items:
        title_el = item.select_one(".Job_opening_item_title a, a[href*='job_id']")
        title = title_el.text.strip() if title_el else ""
        href = title_el.get("href", "") if title_el else ""
        job_id_match = re.search(r"job_id=([^&#]+)", href)
        native_job_id = job_id_match.group(1) if job_id_match else ""

        if not native_job_id or not title:
            continue

        p_id_match = re.search(r"p_id=([^&#]+)", href)
        native_company_id = p_id_match.group(1) if p_id_match else ""

        if native_company_id:
            full_url = f"https://www.yes123.com.tw/wk_index/job.asp?p_id={native_company_id}&job_id={native_job_id}"
        else:
            full_url = f"https://www.yes123.com.tw/wk_index/job.asp?job_id={native_job_id}"

        comp_el = item.select_one("a[href*='comp_info.asp'], a[href*='comp_']")
        company_name = comp_el.text.strip() if comp_el else ""

        pay_el = item.select_one(
            ".Job_opening_item_title_payment, [class*='payment'], [class*='salary']"
        )
        raw_salary = pay_el.text.strip() if pay_el else ""

        date_el = item.select_one(".Job_opening_item_date, [class*='date']")
        appear_date_raw = date_el.text.strip() if date_el else ""

        info_el = item.select_one(".Job_opening_item_info")
        raw_area = ""
        if info_el:
            spans = [s.text.strip() for s in info_el.find_all("span") if s.text.strip()]
            if spans:
                raw_area = spans[0]
        if not raw_area:
            all_texts = list(item.stripped_strings)
            for token in all_texts:
                if re.search(r"(?:市|縣|區|鄉|鎮|海外|洲|國)", token) and not any(
                    k in token
                    for k in ["月薪", "日薪", "時薪", "年薪", "面議", "全職", "兼職", "工程師", "公司", "集團"]
                ):
                    raw_area = token
                    break

        is_tw = is_taiwan_location(raw_area)
        standardized_addr = standardize_taiwan_address(raw_area) if is_tw and raw_area else raw_area
        salary_obs = extract_salary_observations(None, None, raw_salary)

        source_job_key = f"yes123:{native_job_id}"
        source_company_key = f"yes123:{native_company_id}" if native_company_id else ""

        parsed.append({
            "source_platform": "yes123",
            "source_job_key": source_job_key,
            "source_company_key": source_company_key,
            "native_job_id": native_job_id,
            "native_company_id": native_company_id,
            "job_title": title,
            "company_name": company_name,
            "raw_salary": raw_salary,
            "salary_observations": salary_obs,
            "raw_area": raw_area,
            "standardized_address": standardized_addr,
            "is_overseas": not is_tw if raw_area else False,
            "appear_date_raw": appear_date_raw,
            "job_url": full_url,
        })

    return parsed


def parse_job_detail_dom(soup: BeautifulSoup) -> Dict[str, Any]:
    """Parse wk_index/job.asp detailed job specification."""
    job_address = ""
    google_maps_url = None

    for li in soup.find_all("li"):
        title = li.find("span", class_="left_title")
        if title and "工作地點" in title.get_text():
            content = li.find("span", class_="right_main")
            if content:
                a_map = content.find("a", href=True)
                if a_map and "maps.google" in a_map["href"]:
                    google_maps_url = a_map["href"]
                full_text = content.get_text(strip=True)
                if full_text.endswith("地圖"):
                    full_text = full_text[:-2].strip()
                job_address = full_text
            break

    is_tw = is_taiwan_location(job_address)
    computer_skills = []
    work_skills = []
    certs = []
    languages = []

    for li in soup.find_all("li"):
        title = li.find("span", class_="left_title")
        content = li.find("span", class_="right_main")
        if not title or not content:
            continue
        t_text = title.get_text(strip=True)
        c_text = content.get_text(strip=True)
        if "電腦技能" in t_text or "電腦專長" in t_text:
            computer_skills.append(c_text)
        elif "工作技能" in t_text:
            work_skills.append(c_text)
        elif "具備證照" in t_text:
            certs.append(c_text)
        elif "外語能力" in t_text:
            languages.append(c_text)

    return {
        "job_address": job_address,
        "google_maps_url": google_maps_url,
        "is_overseas": not is_tw if job_address else False,
        "computer_skills": computer_skills,
        "work_skills": work_skills,
        "certificates": certs,
        "languages": languages,
    }

