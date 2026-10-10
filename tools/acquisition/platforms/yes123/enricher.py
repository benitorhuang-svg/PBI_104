"""Detail page enricher and geocode resolver for yes123 jobs."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

from .parser import parse_job_detail_dom, is_taiwan_location
from ...shared.geocoding import (
    standardize_taiwan_address,
    normalize_address,
    address_hash,
)

SQLITE_PATH = Path(__file__).resolve().parents[5] / "WGS84_TWD97" / "database.sqlite"
LOCAL_GEOCODER_URL = "http://127.0.0.1:3301/api/geocode"
SQLITE_LOCK = threading.Lock()
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def ensure_enrichment_schema(conn: Any) -> None:
    """Ensure tracking and enrichment tables exist in silver schema."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS silver.job_detail_enrichments (
                job_no TEXT PRIMARY KEY REFERENCES silver.job_current(job_no),
                job_address TEXT,
                is_overseas BOOLEAN NOT NULL DEFAULT FALSE,
                google_maps_url TEXT,
                skills_count INT NOT NULL DEFAULT 0,
                enriched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_detail_enrichments_enriched_at
            ON silver.job_detail_enrichments(enriched_at);
        """)


def extract_coords_from_gmaps_embed(
    url: str, session: requests.Session, timeout: float = 12.0
) -> Tuple[Optional[float], Optional[float]]:
    """Parse global WGS84 coordinates from Google Maps embed page HTML."""
    try:
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        text = resp.text
        # Pattern 1: [lat, lng]
        matches = re.findall(r'\[\s*(-?[0-9]{1,2}\.[0-9]+)\s*,\s*(-?[0-9]{1,3}\.[0-9]+)\s*\]', text)
        for a, b in matches:
            lat, lng = float(a), float(b)
            if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0 and (lat != 0.0 or lng != 0.0):
                return lat, lng
        # Pattern 2: [scale, lng, lat] (categorical/places search in initEmbed)
        m2 = re.findall(r'\[[0-9\.]+\s*,\s*(-?[0-9]{1,3}\.[0-9]{4,})\s*,\s*(-?[0-9]{1,2}\.[0-9]{4,})\s*\]', text)
        for b, a in m2:
            lat, lng = float(a), float(b)
            if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0 and (lat != 0.0 or lng != 0.0):
                return lat, lng
        # Pattern 3: Protocol buffer !3dlat!4dlng
        pb_match = re.findall(r'!3d(-?[0-9]{1,2}\.[0-9]+)!4d(-?[0-9]{1,3}\.[0-9]+)', text)
        for a, b in pb_match:
            lat, lng = float(a), float(b)
            if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
                return lat, lng
    except Exception:
        pass
    return None, None


def write_sqlite_alias(address: str, lat: float, lng: float, db_path: Path = SQLITE_PATH) -> None:
    """Write verified address alias back into local geocoder SQLite database."""
    if not db_path.exists():
        return
    with SQLITE_LOCK:
        try:
            with sqlite3.connect(db_path, timeout=10.0) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO address_aliases (alias_norm, address, lng, lat) VALUES (?, ?, ?, ?)",
                    (address, address, lng, lat),
                )
        except Exception:
            pass


def resolve_address_geocoding(
    address: str,
    gmaps_url: Optional[str],
    session: requests.Session,
    geocoder_url: str = LOCAL_GEOCODER_URL,
) -> Tuple[Optional[Decimal], Optional[Decimal], str, str]:
    """Resolve coordinates via local geocoder first, falling back to Google Maps globally."""
    # 1. Local geocoder query
    try:
        resp = session.get(geocoder_url, params={"q": address}, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get("lat") and data.get("lon"):
                lat = Decimal(str(data["lat"]))
                lng = Decimal(str(data["lon"]))
                return lat, lng, data.get("matchLevel", "POI_ALIAS"), data.get("strategy", "LOCAL_GEOCODER")
    except Exception:
        pass

    # 2. Google Maps Embed Fallback (Global)
    target_url = gmaps_url or f"https://maps.google.com.tw/maps?q={quote(address)}&z=16&output=embed"
    glat, glng = extract_coords_from_gmaps_embed(target_url, session)
    if glat is not None and glng is not None:
        write_sqlite_alias(address, glat, glng)
        return (
            Decimal(str(round(glat, 7))),
            Decimal(str(round(glng, 7))),
            "POI_ALIAS",
            "GOOGLE_MAPS_EMBED_FALLBACK",
        )

    return None, None, "NOT_FOUND", "UNRESOLVED"


def fetch_and_parse_job_detail(
    job_link: str, session: requests.Session, timeout: float = 10.0
) -> Dict[str, Any]:
    """Fetch job detail page HTML and parse DOM components."""
    resp = session.get(job_link, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    return parse_job_detail_dom(soup)


def clean_address_noise(addr: str) -> str:
    """Strip emojis and boilerplate prefix like 上班地點: from raw address string."""
    m = re.search(r"(?:上班地點|工作地點)[:：]\s*(.*)", addr)
    if m:
        addr = m.group(1)
    county_m = list(re.finditer(r"([臺台][北市中南]|(?:基隆|新竹|嘉義)[市縣]|(?:宜蘭|桃園|苗栗|彰化|南投|雲林|屏東|臺東|台東|花蓮|澎湖|金門|連江)[縣市][\u4e00-\u9fff]{1,4}?[區鄉鎮市])", addr))
    if len(county_m) > 1:
        addr = addr[county_m[-1].start():]
    addr = re.sub(r"[【《\[\(].*?[】》\]\)]", "", addr)
    addr = re.sub(r"[^\u4e00-\u9fff\w\d\-#號樓之段巷弄路街大道市縣區鄉鎮村里]", "", addr)
    return addr.strip()


def assemble_full_address(raw_addr: str, fallback_area: str) -> str:
    """Combine district context with street address if missing county prefix."""
    addr = clean_address_noise(raw_addr.strip())
    if not addr:
        return fallback_area.strip()
    if is_taiwan_location(addr):
        if not re.search(r"^[臺台][北市中南]|^(?:基隆|新竹|嘉義)[市縣]|^(?:宜蘭|桃園|苗栗|彰化|南投|雲林|屏東|臺東|台東|花蓮|澎湖|金門|連江)[縣市]", addr):
            prefix_match = re.match(r"^([臺台][北市中南]|(?:基隆|新竹|嘉義)[市縣]|(?:宜蘭|桃園|苗栗|彰化|南投|雲林|屏東|臺東|台東|花蓮|澎湖|金門|連江)[縣市])", fallback_area)
            if prefix_match:
                addr = prefix_match.group(1) + addr
    return addr


def enrich_single_job(
    job_row: Dict[str, Any],
    session: requests.Session,
    geocoder_url: str = LOCAL_GEOCODER_URL,
) -> Dict[str, Any]:
    """Execute complete enrichment pipeline for a single job."""
    job_no = job_row["job_no"]
    job_link = job_row["job_link"]
    fallback_area = job_row.get("source_area") or ""

    detail = fetch_and_parse_job_detail(job_link, session)
    raw_addr = detail.get("job_address") or fallback_area
    is_overseas = detail.get("is_overseas", False) or not is_taiwan_location(raw_addr)
    full_address = raw_addr if is_overseas else assemble_full_address(raw_addr, fallback_area)

    lat: Optional[Decimal] = None
    lng: Optional[Decimal] = None
    match_level = "NOT_FOUND"
    strategy = "UNRESOLVED"

    if full_address:
        lat, lng, match_level, strategy = resolve_address_geocoding(
            full_address, detail.get("google_maps_url"), session, geocoder_url=geocoder_url
        )
        if lat is not None:
            if is_overseas:
                match_level = "POI_ALIAS"
                strategy = "GOOGLE_MAPS_GLOBAL_GEOCODE"
            elif match_level not in {"EXACT_TEXT", "ADDRESS_STANDARDIZED", "ADDRESS_VARIANT", "STREET_FALLBACK", "POI_ALIAS"}:
                match_level = "POI_ALIAS"
        else:
            match_level = "NOT_FOUND"
            strategy = "UNRESOLVED"

    area_key = f"||{full_address}||"
    skills = detail.get("computer_skills", []) + detail.get("work_skills", [])

    return {
        "job_no": job_no,
        "full_address": full_address,
        "is_overseas": is_overseas,
        "google_maps_url": detail.get("google_maps_url"),
        "latitude": lat,
        "longitude": lng,
        "match_level": match_level,
        "strategy": strategy,
        "area_key": area_key,
        "skills": skills,
        "certificates": detail.get("certificates", []),
        "languages": detail.get("languages", []),
    }


def persist_enrichment(conn: Any, result: Dict[str, Any]) -> None:
    """Save enriched address, geocode, and skills into silver tables."""
    akey = result["area_key"]
    addr = result["full_address"]
    lat = result["latitude"]
    lng = result["longitude"]
    mlevel = result["match_level"]
    strat = result["strategy"]
    jno = result["job_no"]

    with conn.cursor() as cur:
        # 1. Update/Insert silver.area_dimension
        cur.execute("""
            INSERT INTO silver.area_dimension (area_key, job_addr_no, job_addr_no_desc, job_address, latitude, longitude)
            VALUES (%s, NULL, NULL, %s, %s, %s)
            ON CONFLICT (area_key) DO UPDATE SET
                job_address = COALESCE(EXCLUDED.job_address, silver.area_dimension.job_address),
                latitude = COALESCE(EXCLUDED.latitude, silver.area_dimension.latitude),
                longitude = COALESCE(EXCLUDED.longitude, silver.area_dimension.longitude)
        """, (akey, addr, lat, lng))

        # 2. Update/Insert silver.address_geocodes
        digest = hashlib.sha256(addr.encode("utf-8")).hexdigest()
        cur.execute("""
            INSERT INTO silver.address_geocodes (
                area_key, address_hash, normalized_address, input_address, matched_address,
                latitude, longitude, match_level, strategy, canonical_address,
                standardization_version, google_maps_search_url, geocoder_name, geocoded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (area_key) DO UPDATE SET
                latitude = COALESCE(EXCLUDED.latitude, silver.address_geocodes.latitude),
                longitude = COALESCE(EXCLUDED.longitude, silver.address_geocodes.longitude),
                match_level = CASE WHEN EXCLUDED.latitude IS NOT NULL THEN EXCLUDED.match_level ELSE silver.address_geocodes.match_level END,
                strategy = CASE WHEN EXCLUDED.latitude IS NOT NULL THEN EXCLUDED.strategy ELSE silver.address_geocodes.strategy END,
                geocoded_at = CURRENT_TIMESTAMP
        """, (
            akey, digest, addr, addr, addr, lat, lng, mlevel, strat,
            addr, "TW-ADDRESS-1", result["google_maps_url"], "wgs84_twd97_plus_gmaps"
        ))

        # 3. Update silver.job_current
        cur.execute("""
            UPDATE silver.job_current
            SET area_key = %s, source_area = %s, updated_at = CURRENT_TIMESTAMP
            WHERE job_no = %s
        """, (akey, addr, jno))

        # 4. Insert checkpoint tracking
        cur.execute("""
            INSERT INTO silver.job_detail_enrichments (
                job_no, job_address, is_overseas, google_maps_url, skills_count, enriched_at
            ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (job_no) DO NOTHING
        """, (jno, addr, result["is_overseas"], result["google_maps_url"], len(result["skills"])))
