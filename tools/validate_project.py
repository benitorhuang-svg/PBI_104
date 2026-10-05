"""Comprehensive validation gate for 104 Power BI intelligence project."""

import glob
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]


def check_sync():
    sys.path.insert(0, str(PROJECT / "tools"))
    from sync_queries import sync
    result = sync(PROJECT, write=False)
    return {
        "passed": len(result["mismatches"]) == 0 and not result["queryOrderChanged"],
        "queries": result["queries"],
        "mismatches": result["mismatches"]
    }


def check_tmdl():
    ps = PROJECT / "tools/desktop_model.ps1"
    res = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Operation", "Parse"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT)
    )
    if res.returncode != 0:
        return {"passed": False, "error": res.stderr.strip() or res.stdout.strip()}
    data = json.loads(res.stdout.strip())
    return {"passed": data.get("Result") == "PASS", "details": data}


def check_pbir_json():
    files = list(PROJECT.glob("PBI_104.Report/**/*.json"))
    invalid = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                json.load(fp)
        except Exception as e:
            invalid.append({"file": str(f.relative_to(PROJECT)), "error": str(e)})
    return {
        "passed": len(invalid) == 0,
        "totalJsonFiles": len(files),
        "invalidFiles": invalid
    }


def check_unit_tests():
    loader = unittest.TestLoader()
    suite = loader.discover(str(PROJECT / "tools/tests"))
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    return {
        "passed": result.wasSuccessful(),
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors)
    }


def check_line_counts():
    scripts = list(PROJECT.glob("tools/**/*.py")) + list(PROJECT.glob("tools/**/*.ps1"))
    violations = []
    for s in scripts:
        lines = len(s.read_text(encoding="utf-8", errors="replace").splitlines())
        if lines > 300:
            violations.append({"file": str(s.relative_to(PROJECT)), "lines": lines})
    return {
        "passed": len(violations) == 0,
        "checkedFiles": len(scripts),
        "violations": violations
    }


def check_live_desktop():
    ps = PROJECT / "tools/desktop_model.ps1"
    res = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", "@(Get-Process msmdsrv -ErrorAction SilentlyContinue).Count"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT)
    )
    count = int(res.stdout.strip() or "0")
    if count != 1:
        return {"available": False, "note": f"msmdsrv instances: {count}"}
    inv = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Operation", "Inventory"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT)
    )
    if inv.returncode != 0:
        return {"available": False, "error": inv.stderr.strip()}
    data = json.loads(inv.stdout.strip())
    return {"available": True, "inventory": data}


def main():
    report = {
        "mExpressionsSync": check_sync(),
        "tmdlSerialization": check_tmdl(),
        "pbirJsonSyntax": check_pbir_json(),
        "unitTests": check_unit_tests(),
        "lineCountsLimit300": check_line_counts(),
        "liveDesktop": check_live_desktop()
    }
    all_passed = (
        report["mExpressionsSync"]["passed"]
        and report["tmdlSerialization"]["passed"]
        and report["pbirJsonSyntax"]["passed"]
        and report["unitTests"]["passed"]
        and report["lineCountsLimit300"]["passed"]
    )
    report["overallPassed"] = all_passed
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
