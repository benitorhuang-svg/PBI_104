import sys
from pathlib import Path
import time
import json
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquisition.platforms.jobwant_104.persistence.loader import read_db_config

ACTIVE_READERS = [
    ("FactJob", "gold.pbi_fact_jobs_report_v22",
     '"jobNo", "custNo", "areaKey", "jobName", "descSnippet", "jobAddress", '
     '"jobAddrNoDesc", "salaryLow", "salaryHigh", "appearDate", "jobLink", '
     '"snapshotDate", "snapshotDateTime", "sourcePlatform"'),
    ("DimCompany", "gold.pbi_dim_company_v21", "*"),
    ("DimArea", "gold.pbi_dim_area_v22", "*"),
    ("DimDate", "gold.pbi_dim_date_v21", "*"),
    ("DimSkill", "gold.pbi_dim_skill_v21", "*"),
    ("DimJobCategory", "gold.pbi_dim_job_category_v21", "*"),
    ("BridgeJobSkill", "gold.pbi_bridge_job_skill_keys_v21", "*"),
    ("BridgeJobCategory", "gold.pbi_bridge_job_category_keys_v21", "*"),
    ("FactAcquisitionCategory", "gold.pbi_acquisition_categories", "*"),
    ("DimPlatform", "gold.pbi_dim_platform_v21", "*"),
]


def run_benchmark(env_file=None, runs=3):
    cfg = read_db_config(env_file or ".env")
    results = []
    with psycopg.connect(**cfg) as conn:
        # warm-up query
        conn.execute("SELECT 1")
        for label, view, cols in ACTIVE_READERS:
            samples = []
            last_plan = None
            for _ in range(runs):
                sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT {cols} FROM {view}"
                t0 = time.perf_counter()
                res = conn.execute(sql).fetchone()[0]
                t1 = time.perf_counter()
                plan_data = res[0]
                last_plan = plan_data
                samples.append({
                    "exec_time_ms": plan_data["Execution Time"],
                    "plan_time_ms": plan_data["Planning Time"],
                    "client_elapsed_ms": (t1 - t0) * 1000,
                })
            exec_times = [s["exec_time_ms"] for s in samples]
            plan = last_plan["Plan"]
            results.append({
                "label": label,
                "view": view,
                "actual_rows": plan.get("Actual Rows", 0),
                "plan_node_type": plan.get("Node Type"),
                "median_exec_ms": sorted(exec_times)[len(exec_times) // 2],
                "min_exec_ms": min(exec_times),
                "max_exec_ms": max(exec_times),
                "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
                "shared_read_blocks": plan.get("Shared Read Blocks", 0),
                "temp_read_blocks": plan.get("Temp Read Blocks", 0),
                "temp_written_blocks": plan.get("Temp Written Blocks", 0),
                "samples": samples,
            })
    return results


def main():
    print("Running benchmark on 9 active Gold views (3 runs each)...")
    results = run_benchmark()
    # Sort by median_exec_ms descending to rank bottlenecks
    results.sort(key=lambda x: x["median_exec_ms"], reverse=True)
    print("\n=== RANKED BOTTLENECKS (MEDIAN EXECUTION TIME) ===")
    for rank, r in enumerate(results, 1):
        print(
            f"{rank}. {r['label']:<24} ({r['view']}): "
            f"rows={r['actual_rows']:<8} "
            f"median={r['median_exec_ms']:>8.2f}ms "
            f"(min={r['min_exec_ms']:.2f}ms, max={r['max_exec_ms']:.2f}ms) "
            f"temp_write={r['temp_written_blocks']} blks"
        )
    return results


if __name__ == "__main__":
    main()
