"""Local WGS84_TWD97 geocoder client and address enrichment helpers."""

from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import unicodedata
from urllib.parse import quote
from urllib.request import Request, urlopen


BATCH_SIZE = 2000
MATCH_LEVELS = {"EXACT_TEXT", "ADDRESS_VARIANT", "STREET_FALLBACK", "POI_ALIAS"}
ADDRESS_STANDARDIZATION_VERSION = "TW-ADDRESS-1"
CHINESE_DIGITS = {"〇": "0", "零": "0", "一": "1", "壹": "1", "二": "2",
                  "貳": "2", "兩": "2", "三": "3", "參": "3", "四": "4",
                  "肆": "4", "五": "5", "伍": "5", "六": "6", "陸": "6",
                  "七": "7", "柒": "7", "八": "8", "捌": "8", "九": "9", "玖": "9"}
CHINESE_NUMBER_CHARACTERS = "〇零一壹二貳兩三參四肆五伍六陸七柒八捌九玖十百千"


def _chinese_number_to_ascii(value):
    if not any(unit in value for unit in ("十", "百", "千")):
        digits = "".join(CHINESE_DIGITS[char] for char in value)
        return digits.lstrip("0") or "0"
    total = section = 0
    for char in value:
        if char in CHINESE_DIGITS:
            section = int(CHINESE_DIGITS[char])
        elif char in {"十", "百", "千"}:
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            total += (section or 1) * unit
            section = 0
        else:
            return value
    return str(total + section)


def standardize_taiwan_address(value):
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).replace("台", "臺")
    text = re.sub(r"(?<=\d)-(?=\d)", "之", text)
    text = re.sub(rf"[{CHINESE_NUMBER_CHARACTERS}]+(?=[段巷弄鄰號樓室之-])",
                  lambda match: _chinese_number_to_ascii(match.group()), text)
    text = re.sub(r"(?<!\d)0+(\d+)(?=(?:段|巷|弄|鄰|號|樓|室|之))", r"\1", text)
    return re.sub(r"[\s\u3000，,、]", "", text).strip()


def address_equivalence_key(value):
    text = standardize_taiwan_address(value)
    text = re.sub(r"(?<=[縣市區鄉鎮])[^縣市區鄉鎮]{1,6}(?:村|里)(?:\d{1,3}鄰)?", "", text)
    text = re.sub(r"\d{1,3}鄰", "", text)
    return "".join(char for char in text.casefold()
                   if unicodedata.category(char)[0] in {"L", "N"})


def addresses_equivalent_after_standardization(left, right):
    left_text, right_text = standardize_taiwan_address(left), standardize_taiwan_address(right)
    village_pattern = r"(?<=[縣市區鄉鎮])([^縣市區鄉鎮]{1,6}?)(?:村|里)"
    left_villages = re.findall(village_pattern, left_text)
    right_villages = re.findall(village_pattern, right_text)
    left_neighbors = re.findall(r"(\d{1,3})鄰", left_text)
    right_neighbors = re.findall(r"(\d{1,3})鄰", right_text)
    if left_villages and right_villages and left_villages != right_villages:
        return False
    if left_neighbors and right_neighbors and left_neighbors != right_neighbors:
        return False
    return address_equivalence_key(left_text) == address_equivalence_key(right_text)


def street_lookup_query(value):
    text = standardize_taiwan_address(value)
    match = re.match(
        r"^[\u4e00-\u9fff]{1,6}?[縣市][\u4e00-\u9fff]{1,8}?(?:區|鄉|鎮|市)(?![區鄉鎮市])(.*)$",
        text)
    if not match:
        return text
    street = match.group(1)
    street = re.sub(r"^(?:[^縣市區鄉鎮]{1,6}(?:村|里))?(?:\d{1,3}鄰)?", "", street)
    return street or text


def is_plausible_taiwan_address(value):
    text = standardize_taiwan_address(value)
    return (bool(re.search(r"[\u4e00-\u9fff]{1,5}[縣市]", text))
            and bool(re.search(r"[\u4e00-\u9fff]{1,5}(?:區|鄉|鎮|市)", text))
            and bool(re.search(r"(?:路|街|大道)", text))
            and bool(re.search(r"\d+(?:之\d+)?號", text)))


def google_maps_search_url(value):
    if not is_plausible_taiwan_address(value):
        return None
    return "https://www.google.com/maps/search/?api=1&query=" + quote(
        standardize_taiwan_address(value), safe="")


def normalize_address(value):
    text = standardize_taiwan_address(value).casefold()
    return "".join(char for char in text if unicodedata.category(char)[0] in {"L", "N"})


def address_hash(value):
    normalized = normalize_address(value)
    if not normalized:
        raise ValueError("Address is empty after normalization")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def group_candidates(rows):
    groups = {}
    for row in rows:
        if len(row) == 2:
            area_key, address = row
        else:
            area_key, description, address = row
            description = standardize_taiwan_address(description or "")
            address = standardize_taiwan_address(address or "")
            if (description and re.search(r"(?:市|縣).*(?:區|鄉|鎮|市)$", description)
                    and re.search(r"(?:路|街|大道).*\d+號", address)
                    and not address.startswith(description)):
                address = description + address
        if not isinstance(address, str) or not normalize_address(address):
            continue
        canonical = standardize_taiwan_address(address)
        key = normalize_address(address)
        group = groups.setdefault(key, {"input_address": canonical, "areas": []})
        group["areas"].append({"area_key": area_key, "input_address": address.strip()})
    return [{"normalized_address": key, "canonical_address": groups[key]["input_address"],
             "geocoder_query": street_lookup_query(groups[key]["input_address"]),
             **groups[key]} for key in sorted(groups)]


def chunks(values, size=BATCH_SIZE):
    if size < 1 or size > BATCH_SIZE:
        raise ValueError(f"Batch size must be between 1 and {BATCH_SIZE}")
    for start in range(0, len(values), size):
        yield values[start:start + size]


def validate_result(result):
    if result is None:
        return {"matched_address": None, "latitude": None, "longitude": None,
                "match_level": "NOT_FOUND", "strategy": None}
    if not isinstance(result, dict):
        raise ValueError("Geocoder result must be an object or null")
    match_level = result.get("matchLevel")
    if match_level not in MATCH_LEVELS:
        raise ValueError(f"Unsupported geocoder matchLevel: {match_level!r}")
    try:
        longitude = Decimal(str(result["lon"]))
        latitude = Decimal(str(result["lat"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Geocoder result has invalid WGS84 coordinates") from error
    if (not longitude.is_finite() or not latitude.is_finite()
            or not Decimal(-180) <= longitude <= Decimal(180)
            or not Decimal(-90) <= latitude <= Decimal(90)
            or (longitude == 0 and latitude == 0)):
        raise ValueError("Geocoder result has out-of-range or unusable coordinates")
    matched_address = result.get("address")
    if not isinstance(matched_address, str) or not matched_address.strip():
        raise ValueError("Geocoder result has no matched address")
    strategy = result.get("strategy")
    if strategy is not None and not isinstance(strategy, str):
        raise ValueError("Geocoder strategy must be text")
    return {"matched_address": matched_address, "latitude": latitude,
            "longitude": longitude, "match_level": match_level, "strategy": strategy}


def geocode_batch(base_url, addresses, opener=urlopen):
    url = base_url.rstrip("/") + "/api/geocode/batch"
    request = Request(url, data=json.dumps({"addresses": addresses}, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    with opener(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or len(results) != len(addresses):
        raise ValueError("Geocoder response count does not match request count")
    return [validate_result(item) for item in results]


def geocode_candidates(base_url, candidates, opener=urlopen):
    addresses = [item["geocoder_query"] for item in candidates]
    results = []
    for batch in chunks(addresses):
        results.extend(geocode_batch(base_url, batch, opener))
    if len(results) != len(candidates):
        raise ValueError("Geocoder returned an incomplete candidate set")

    def upgrade_standardized(candidate, result):
        if (result["match_level"] == "ADDRESS_VARIANT"
                and addresses_equivalent_after_standardization(
                    candidate["canonical_address"], result["matched_address"])):
            result["match_level"] = "ADDRESS_STANDARDIZED"

    for candidate, result in zip(candidates, results):
        upgrade_standardized(candidate, result)

    retry_indexes = [index for index, (candidate, result) in enumerate(zip(candidates, results))
                     if result["match_level"] == "NOT_FOUND"
                     and candidate["canonical_address"] != candidate["geocoder_query"]]
    retry_queries = [candidates[index]["canonical_address"] for index in retry_indexes]
    retry_results = []
    for batch in chunks(retry_queries):
        retry_results.extend(geocode_batch(base_url, batch, opener))
    if len(retry_results) != len(retry_indexes):
        raise ValueError("Geocoder returned an incomplete contextual retry set")
    for index, result in zip(retry_indexes, retry_results):
        upgrade_standardized(candidates[index], result)
        if result["match_level"] != "NOT_FOUND":
            results[index] = result
    return results


def stored_rows(candidates, results):
    if len(candidates) != len(results):
        raise ValueError("Candidate and geocoder result counts differ")
    rows = []
    for candidate, result in zip(candidates, results):
        digest = address_hash(candidate["input_address"])
        for area in candidate["areas"]:
            rows.append((area["area_key"], digest, candidate["normalized_address"],
                         area["input_address"], result["matched_address"], result["latitude"],
                         result["longitude"], result["match_level"], result["strategy"],
                         candidate["canonical_address"], ADDRESS_STANDARDIZATION_VERSION,
                         google_maps_search_url(candidate["canonical_address"])
                         if result["match_level"] == "NOT_FOUND" else None))
    return rows
