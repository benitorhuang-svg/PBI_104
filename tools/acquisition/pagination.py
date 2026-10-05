"""Technical pagination contracts shared by acquisition and its tests."""


def integer(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    if value < minimum or value != int(value):
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return int(value)


def validate_page(payload, requested, expected=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Expected an object containing $.data array")
    if any(not isinstance(row, dict) for row in payload["data"]):
        raise ValueError("Every $.data item must be an object")
    metadata = payload.get("metadata")
    pagination = metadata.get("pagination") if isinstance(metadata, dict) else None
    if not isinstance(pagination, dict):
        raise ValueError("Missing $.metadata.pagination object")
    values = {name: integer(pagination.get(name), name)
              for name in ("currentPage", "lastPage", "total", "count")}
    if values["currentPage"] != requested:
        raise ValueError(f"Page mismatch: requested {requested}")
    if values["count"] != len(payload["data"]):
        raise ValueError(f"Row/count mismatch on page {requested}")
    if values["total"] == 0:
        if values["lastPage"] != 0 or values["count"] != 0:
            raise ValueError("Inconsistent empty pagination")
    elif values["lastPage"] < requested or values["count"] == 0:
        raise ValueError("Unexpected empty or out-of-range page")
    if expected and any(values[name] != expected[name] for name in ("lastPage", "total")):
        raise ValueError("Pagination changed during acquisition; retry the whole batch")
    return values


def collect(fetch, start=1, max_pages=1000):
    start = integer(start, "start", 1)
    max_pages = integer(max_pages, "max_pages", 1)
    first = fetch(start)
    expected = validate_page(first["response"], start)
    last = expected["lastPage"]
    if last - start + 1 > max_pages:
        raise ValueError("Configured page guard exceeded")
    pages = [first]
    for page in range(start + 1, last + 1):
        result = fetch(page)
        validate_page(result["response"], page, expected)
        pages.append(result)
    returned = sum(len(page["response"]["data"]) for page in pages)
    if start == 1 and returned != expected["total"]:
        raise ValueError("Incomplete batch: returned rows do not match total")
    return pages
