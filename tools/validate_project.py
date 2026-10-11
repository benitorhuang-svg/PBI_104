"""Run deterministic offline project checks plus official cached PBIR schemas."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from copy import deepcopy
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urldefrag, urlparse
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".optimization/schema-cache"
SCHEMA_FALLBACKS: dict[str, str] = {}
sys.path.insert(0, str(ROOT / ".optimization/deps"))
sys.path.insert(0, str(ROOT / "tools"))


def official_schema(url: str) -> dict:
    url, _ = urldefrag(url)
    if urlparse(url).scheme != "https" or urlparse(url).hostname != "developer.microsoft.com":
        raise ValueError(f"PBIR schema host is not the official Microsoft schema host: {url}")
    cached = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    compatibility_file = cached.with_suffix(".compatibility.json")
    if cached.exists():
        if compatibility_file.exists():
            SCHEMA_FALLBACKS.update(json.loads(compatibility_file.read_text(encoding="utf-8")))
        elif url.endswith("/visualContainer/2.13.0/schema.json"):
            fallback_url = url.replace("/2.13.0/", "/2.12.0/")
            SCHEMA_FALLBACKS[url] = fallback_url
            compatibility_file.write_text(json.dumps(SCHEMA_FALLBACKS), encoding="utf-8")
        return json.loads(cached.read_text(encoding="utf-8"))
    try:
        with urlopen(url, timeout=30) as response:
            content = response.read()
        schema = json.loads(content.decode("utf-8-sig"))
    except HTTPError as error:
        if not url.endswith("/visualContainer/2.13.0/schema.json"):
            raise RuntimeError(f"Could not fetch official Microsoft schema {url}: {error}") from error
        if error.code != 404:
            raise RuntimeError(f"Official Microsoft schema request failed with HTTP {error.code}: {url}") from error
        fallback_url = url.replace("/2.13.0/", "/2.12.0/")
        with urlopen(fallback_url, timeout=30) as response:
            schema = json.loads(response.read().decode("utf-8-sig"))
        schema = deepcopy(schema)
        schema["$id"] = url
        schema.get("properties", {}).get("$schema", {})["const"] = url
        SCHEMA_FALLBACKS[url] = fallback_url
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    if url in SCHEMA_FALLBACKS:
        compatibility_file.write_text(json.dumps({url: SCHEMA_FALLBACKS[url]}), encoding="utf-8")
    return schema


def check_json() -> int:
    files = [ROOT / "PBI_JobWant.pbip"]
    files += list((ROOT / "PBI_JobWant.Report/definition").rglob("*.json"))
    files += list((ROOT / "PBI_JobWant.SemanticModel/definition").rglob("*.json"))
    for path in files:
        with path.open("r", encoding="utf-8-sig") as source:
            json.load(source)
    return len(files)


def check_project_artifact_paths() -> int:
    project = json.loads((ROOT / "PBI_JobWant.pbip").read_text(encoding="utf-8-sig"))
    root = ROOT.resolve()
    checked = 0
    for artifact in project.get("artifacts", []):
        report = artifact.get("report")
        if not isinstance(report, dict) or not isinstance(report.get("path"), str):
            raise ValueError("PBIP artifact is missing its report path")
        report_path = (root / report["path"]).resolve()
        if not report_path.is_relative_to(root) or not report_path.is_dir():
            raise ValueError(f"PBIP report path is invalid: {report['path']}")
        report_file = report_path / "definition.pbir"
        if not report_file.is_file():
            raise ValueError(f"PBIR definition is missing: {report_file.relative_to(root)}")
        report_definition = json.loads(report_file.read_text(encoding="utf-8-sig"))
        model_reference = report_definition.get("datasetReference", {}).get("byPath", {}).get("path")
        if not isinstance(model_reference, str):
            raise ValueError(f"PBIR semantic-model path is missing: {report_file.relative_to(root)}")
        model_path = (report_path / model_reference).resolve()
        if not model_path.is_relative_to(root) or not (model_path / "definition.pbism").is_file():
            raise ValueError(f"PBIR semantic-model path is invalid: {model_reference}")
        checked += 2
    if checked == 0:
        raise ValueError("PBIP contains no report-to-semantic-model paths")
    return checked


def report_symbols() -> dict[str, set[str]]:
    symbols: dict[str, set[str]] = {}
    for table in (ROOT / "PBI_JobWant.SemanticModel/definition/tables").glob("*.tmdl"):
        text = table.read_text(encoding="utf-8-sig")
        name = re.search(r"(?m)^table (.+)$", text)
        if not name:
            continue
        columns = re.findall(
            r"(?m)^\tcolumn (?:'([^']+)'|([^=\r\n]+?))(?:\s*=\s*)?$",
            text,
        )
        values = {quoted or unquoted.strip() for quoted, unquoted in columns}
        measures = re.findall(r"(?m)^\tmeasure (?:'([^']+)'|([^=\r\n]+?))\s*=", text)
        values |= {quoted or unquoted.strip() for quoted, unquoted in measures}
        symbols[name[1]] = values
    return symbols


def check_report_references() -> int:
    symbols = report_symbols()
    checked = 0
    for path in (ROOT / "PBI_JobWant.Report/definition/pages").rglob("visual.json"):
        visual = json.loads(path.read_text(encoding="utf-8-sig"))

        def visit(value):
            nonlocal checked
            if isinstance(value, dict):
                for kind in ("Column", "Measure"):
                    field = value.get(kind)
                    if not isinstance(field, dict):
                        continue
                    source = field.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    prop = field.get("Property")
                    if source and prop:
                        checked += 1
                        if prop not in symbols.get(source, set()):
                            raise ValueError(f"{path.relative_to(ROOT)} refers to missing {source}.{prop}")
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(visual.get("visual", {}))
    return checked


def check_schemas() -> int:
    jsonschema = importlib.import_module("jsonschema")
    from referencing import Registry, Resource

    schemas: dict[str, dict] = {}

    def retrieve(uri):
        url, fragment = urldefrag(str(uri))
        if url not in schemas:
            schemas[url] = official_schema(url)
        schema = schemas[url]
        return Resource.from_contents(schema)

    registry = Registry(retrieve=retrieve)
    checked = 0
    for path in (ROOT / "PBI_JobWant.Report/definition").rglob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        schema_url = document.get("$schema")
        if not schema_url:
            continue
        schema = official_schema(schema_url)
        validator = jsonschema.validators.validator_for(schema)(schema, registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            raise ValueError(f"{path.relative_to(ROOT)}: {list(error.path)}: {error.message}")
        checked += 1
    return checked


def main() -> int:
    json_files = check_json()
    artifact_links = check_project_artifact_paths()
    references = check_report_references()
    schemas = check_schemas()
    from sync_queries import sync

    sync_result = sync(ROOT)
    if sync_result["mismatches"] or sync_result["queryOrderChanged"]:
        raise ValueError(f"M exports are out of sync with TMDL: {sync_result}")
    for path in (ROOT / "tools").rglob("*.py"):
        if len(path.read_text(encoding="utf-8-sig").splitlines()) > 300:
            raise ValueError(f"Maintained Python file exceeds 300 lines: {path.relative_to(ROOT)}")
    desktop_parse = "UNAVAILABLE"
    validation_scope = "STRUCTURE_ONLY"
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell and os.name == "nt":
        result = subprocess.run(
            [powershell, "-NoProfile", "-File", str(ROOT / "tools/desktop/desktop_model.ps1"), "-Operation", "Parse"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        desktop_parse = json.loads(result.stdout).get("Result", "FAIL")
        if desktop_parse != "PASS":
            raise RuntimeError(f"Desktop TMDL parser did not pass: {desktop_parse}")
        validation_scope = "STRUCTURE_AND_DESKTOP_TMDL"
    result_status = "PASS" if desktop_parse == "PASS" else "STRUCTURE_PASS_DESKTOP_TMDL_UNAVAILABLE"
    print(json.dumps({"result": result_status, "validationScope": validation_scope,
                      "structuralChecks": "PASS", "jsonFiles": json_files, "pbirSchemas": schemas,
                      "projectArtifactLinks": artifact_links,
                      "reportFieldReferences": references, "queries": sync_result["queries"],
                      "desktopTmdlParser": desktop_parse,
                      "schemaCompatibility": SCHEMA_FALLBACKS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
