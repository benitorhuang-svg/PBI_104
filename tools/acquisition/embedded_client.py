"""Reuse the project's proven Python.Execute client without duplicating HTTP code."""

import ast
import json
import re

import pandas as pd


def client_code(project):
    source = (project / "powerquery/01_functions/fx104GetPage.pq").read_text(encoding="utf-8-sig")
    match = re.search(r'Python.Execute\(\s*"((?:[^"]|"")*)",\s*\[config', source, re.S)
    if not match:
        raise ValueError("Cannot locate the trusted Python.Execute client")
    code = match[1].replace('""', '"')
    ast.parse(code)
    return compile(code, "fx104GetPage.pq/Python.Execute", "exec")


def fetch_page(code, request, page):
    config = {"baseUrl": request["baseUrl"], "keyword": request["keyword"],
              "area": request["area"], "jobsource": request["jobsource"],
              "mode": request["mode"], "order": request["order"],
              "page": page, "pagesize": request["pagesize"]}
    namespace = {"config": pd.DataFrame([config])}
    exec(code, namespace)
    response = json.loads(namespace["df_raw_response"].iloc[0]["rawResponseJson"])
    metadata = namespace["df_metadata"].iloc[0].to_dict()
    metadata = {key: (value.item() if hasattr(value, "item") else value)
                for key, value in metadata.items()}
    return {"response": response, "technical": metadata}
