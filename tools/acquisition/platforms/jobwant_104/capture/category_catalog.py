"""Fetch, validate, and preserve 104's official occupational-category catalogue."""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import uuid


SOURCE_URL = "https://static.104.com.tw/category-tool/json/JobCat.json"


def flatten_catalog(payload):
    if not isinstance(payload, list) or not payload:
        raise ValueError("104 category catalogue must be a non-empty root array")
    rows, seen = [], set()

    def visit(items, parent=None, path=()):
        if not isinstance(items, list):
            raise ValueError("Every category children field must be an array")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Every category must be an object")
            code, name = item.get("no"), item.get("des")
            if not isinstance(code, (str, int)) or isinstance(code, bool) or not str(code).isdigit():
                raise ValueError("Category no must be a numeric identifier")
            code = str(code)
            if code in seen or not isinstance(name, str) or not name.strip():
                raise ValueError("Category identifiers must be unique and names non-empty")
            english = item.get("eng")
            if english is not None and not isinstance(english, str):
                raise ValueError(f"Category eng label must be text or null: {code}")
            children = item.get("n", [])
            if not isinstance(children, list):
                raise ValueError(f"Category children must be an array: {code}")
            codes = path + (code,)
            seen.add(code)
            rows.append({"job_cat_code": int(code), "code": code, "name": name.strip(),
                         "english_name": english.strip() if english and english.strip() else None,
                         "parent_code": parent, "depth": len(path), "path_codes": list(codes),
                         "is_leaf": not children})
            visit(children, code, codes)

    visit(payload)
    return rows


def _lake_root(data_root):
    root = Path(data_root).resolve()
    return root if (root / "series").is_dir() or (root / "categories").is_dir() else root / "104"


def fetch_official_catalog():
    import cloudscraper

    proxies = {key: value for key, value in urllib.request.getproxies().items()
               if key.lower() in ("http", "https")}
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows",
                                                    "desktop": True})
    scraper.proxies.update(proxies)
    response = scraper.get(SOURCE_URL, headers={"Accept": "application/json",
                            "Referer": "https://www.104.com.tw/jobs/search/"}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = flatten_catalog(payload)
    return {"payload": payload, "content": response.content, "rows": rows,
            "captured_at": datetime.now().astimezone().isoformat(timespec="seconds")}


def write_catalog_snapshot(data_root, fetched):
    root = _lake_root(data_root) / "reference" / "job-categories"
    root.mkdir(parents=True, exist_ok=True)
    content = fetched["content"]
    digest = hashlib.sha256(content).hexdigest()
    moment = datetime.fromisoformat(fetched["captured_at"])
    stem = moment.strftime("%Y%m%dT%H%M%S%z") + "-" + digest[:12]
    data_path = root / f"{stem}.json"
    manifest_path = root / f"{stem}.manifest.json"
    if data_path.exists() and hashlib.sha256(data_path.read_bytes()).hexdigest() != digest:
        raise ValueError("Refusing to overwrite a different category catalogue snapshot")
    if not data_path.exists():
        temporary = root / ("." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, data_path)
        finally:
            temporary.unlink(missing_ok=True)
    manifest = {"schemaVersion": 1, "sourceUrl": SOURCE_URL,
                "capturedAt": fetched["captured_at"], "file": data_path.name,
                "sha256": digest, "rootCount": len(fetched["payload"]),
                "rowCount": len(fetched["rows"])}
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if manifest_path.exists() and manifest_path.read_bytes() != encoded:
        raise ValueError("Refusing to overwrite a different catalogue manifest")
    if not manifest_path.exists():
        temporary = root / ("." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"manifest": manifest, "rows": fetched["rows"], "payload": fetched["payload"]}


def read_latest_catalog(data_root):
    root = _lake_root(data_root) / "reference" / "job-categories"
    manifests = sorted(root.glob("*.manifest.json"), reverse=True) if root.is_dir() else []
    if not manifests:
        return None
    path = manifests[0]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or manifest.get("sourceUrl") != SOURCE_URL:
        raise ValueError(f"Unsupported 104 category manifest: {path}")
    name = manifest.get("file")
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError(f"Unsafe category catalogue path: {path}")
    content = (root / name).read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest.get("sha256"):
        raise ValueError(f"Category catalogue checksum mismatch: {path}")
    payload = json.loads(content)
    rows = flatten_catalog(payload)
    if len(rows) != manifest.get("rowCount") or len(payload) != manifest.get("rootCount"):
        raise ValueError(f"Category catalogue count mismatch: {path}")
    return {"manifest": manifest, "payload": payload, "rows": rows}
