"""Check or synchronize complete M exports while preserving existing lineage tags."""

import argparse
import json
from pathlib import Path
import re
import uuid

GROUPS = {"00_parameters": "00_Parameters", "01_functions": "01_Functions",
          "02_source": "02_Source", "03_staging": "03_Staging", "04_model": "04_Model"}
BLOCK = re.compile(r"^expression (\w+) =(.*?)(?=^expression |\Z)", re.M | re.S)


def split_expression(match):
    body = match[2]
    metadata_start = re.search(r"(?m)^\t(?:lineageTag:|queryGroup:)", body)
    if not metadata_start:
        raise ValueError(f"Expression metadata missing: {match[1]}")
    code = body[:metadata_start.start()].strip()
    if code.startswith("```"):
        code = code[3:].strip()
        if not code.endswith("```"):
            raise ValueError("Unclosed TMDL expression fence")
        code = code[:-3].rstrip()
    code = "\n".join(line[2:] if line.startswith("\t\t") else line for line in code.splitlines())
    return code.strip(), body[metadata_start.start():].strip("\n")


def expressions(root):
    path = root / "PBI_104.SemanticModel/definition/expressions.tmdl"
    original = path.read_text(encoding="utf-8-sig")
    existing = {m[1]: m for m in BLOCK.finditer(original)}
    if len(existing) != len(re.findall(r"^expression ", original, re.M)):
        raise ValueError("Unexpected expression format; preserve the file and inspect it")
    rendered = []
    names = []
    mismatches = []
    for directory, group in GROUPS.items():
        for source in sorted((root / "powerquery" / directory).glob("*.pq")):
            name = ("mdl_" if directory == "04_model" else "") + source.stem
            names.append(name)
            code = source.read_text(encoding="utf-8-sig").strip()
            match = existing.get(name)
            if match:
                old_code, metadata = split_expression(match)
                metadata = re.sub(r"(?m)^\tqueryGroup: .*", "\tqueryGroup: " + group, metadata)
                if [line.rstrip() for line in code.splitlines()] != [line.rstrip() for line in old_code.splitlines()]:
                    mismatches.append(name)
            else:
                metadata = "\tlineageTag: " + str(uuid.uuid4()) + "\n\tqueryGroup: " + group
                mismatches.append(name)
            body = "\n".join("\t\t" + line if line.strip() else "" for line in code.splitlines())
            rendered.append("expression " + name + " = ```\n" + body + "\n\t\t```\n" + metadata + "\n")
    extra = set(existing) - set(names)
    mismatches.extend(sorted(extra))
    return path, "\n".join(rendered), names, mismatches


def sync(root, write=False):
    path, content, names, mismatches = expressions(root)
    model_path = root / "PBI_104.SemanticModel/definition/model.tmdl"
    model = model_path.read_text(encoding="utf-8-sig")
    order_match = re.search(r"(?m)^annotation PBI_QueryOrder = (.+)$", model)
    old_order = json.loads(order_match[1])
    table_names = set(re.findall(r"(?m)^ref table (.+)$", model))
    preserved_tables = [name for name in old_order if name not in names and name in table_names]
    legacy_query_tables = [name for name in old_order if name not in names and name == "查詢"]
    order = names + preserved_tables + [name for name in legacy_query_tables if name not in preserved_tables]
    updated = model[:order_match.start(1)] + json.dumps(order, ensure_ascii=False) + model[order_match.end(1):]
    if write:
        path.write_text(content, encoding="utf-8", newline="\n")
        model_path.write_text(updated, encoding="utf-8", newline="\n")
    return {"queries": len(names), "mismatches": mismatches, "queryOrderChanged": order != old_order}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = sync(Path(__file__).resolve().parents[1], args.write)
    print(json.dumps(result, ensure_ascii=False))
    if not args.write and (result["mismatches"] or result["queryOrderChanged"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
