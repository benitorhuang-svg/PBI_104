"""Conservative, deterministic salary observations from 104 fields and text."""

from decimal import Decimal, InvalidOperation
import re

PARSER_VERSION = "1.1.2"
AMOUNT = re.compile(
    r"(?P<currency>NT\$|NTD|TWD|US\$|USD|RMB|新台幣|台幣|美元|人民幣)?\s*"
    r"(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:萬|万|千|[kK])?|"
    r"[零〇一二兩两三四五六七八九十百千萬万]+)\s*(?P<unit>元|圓|块|塊)?",
    re.IGNORECASE)
NEGOTIABLE = re.compile(r"面議|面洽|待遇另議|薪資另議|可議", re.IGNORECASE)
NOT_DISCLOSED = re.compile(r"依公司規定|薪資保密|待遇保密|薪資不公開|待遇不公開")
PAY_CUE = re.compile(r"薪|待遇|報酬|每小時|每月|每年|每週|每周|面議|面洽|薪資保密|待遇保密")
BOUND = re.compile(r"以上|起薪?|至少|最低|最少|以下|至多|最高|不超過|上限")
RANGE = re.compile(r"至|到|~|～|－|—|–|-")
PERIODS = (
    ("HOUR", re.compile(r"時薪|每小時|每鐘頭|小時|[/／]時|[/／]小時|[/／]hr\b|[/／]hour\b", re.I)),
    ("MONTH", re.compile(r"月薪|每月|[/／]月")),
    ("YEAR", re.compile(r"年薪|每年|[/／]年")),
    ("DAY", re.compile(r"日薪|每日|每天|[/／]日")),
    ("WEEK", re.compile(r"週薪|周薪|每週|每周|[/／]週|[/／]周")),
)
CURRENCY = (
    ("TWD", re.compile(r"NT\$|NTD|TWD|新台幣|台幣|元|圓|塊", re.IGNORECASE)),
    ("USD", re.compile(r"US\$|USD|美元", re.IGNORECASE)),
    ("CNY", re.compile(r"RMB|人民幣", re.IGNORECASE)),
)
CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "两": 2,
                  "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _chinese_number(token):
    total = section = digit = 0
    for char in token:
        if char in CHINESE_DIGITS:
            digit = CHINESE_DIGITS[char]
        elif char in "十百千":
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            section += (digit or (1 if char == "十" else 0)) * unit
            digit = 0
        elif char in "萬万":
            section += digit
            total += (section or 1) * 10000
            section = digit = 0
    return Decimal(total + section + digit)


def _amount(token):
    original = token.strip()
    if not re.fullmatch(r"[\d,.]+(?:萬|万|千|[kK])?", original):
        return _chinese_number(original)
    text = original.replace(",", "")
    multiplier = Decimal(1)
    if text[-1:] in ("萬", "万"):
        multiplier, text = Decimal(10000), text[:-1].strip()
    elif text[-1:] == "千":
        multiplier, text = Decimal(1000), text[:-1].strip()
    elif text[-1:].lower() == "k":
        multiplier, text = Decimal(1000), text[:-1].strip()
    try:
        return Decimal(text) * multiplier
    except InvalidOperation:
        return None


def _period(text):
    matches = [name for name, pattern in PERIODS if pattern.search(text)]
    return matches[0] if len(matches) == 1 else "UNKNOWN"


def _currency(text, amount_matches):
    matches = [code for code, pattern in CURRENCY if pattern.search(text)]
    if len(matches) == 1:
        return matches[0], "EXPLICIT_TEXT", False
    if len(matches) > 1:
        return None, "UNKNOWN", True
    if any(match.group("unit") for match in amount_matches):
        return "TWD", "EXPLICIT_TEXT", False
    return "TWD", "PLATFORM_DEFAULT", False


def _component(text):
    if re.search(r"獎金|抽成|佣金|業績獎金|績效獎金", text):
        return "VARIABLE"
    if re.search(r"底薪|基本薪資|本薪|月薪|時薪|年薪|日薪|週薪|周薪", text):
        return "BASE"
    return "UNKNOWN"


def _chunks(text):
    start = 0
    for match in re.finditer(r"[。；;，\r\n]+", text):
        yield start, text[start:match.start()]
        start = match.end()
    yield start, text[start:]


def _description_observations(description):
    observations = []
    if not description:
        return observations
    for start, chunk in _chunks(description):
        left = len(chunk) - len(chunk.lstrip())
        phrase = chunk.strip()
        if not phrase:
            continue
        numbers = list(AMOUNT.finditer(phrase))
        negotiated = bool(NEGOTIABLE.search(phrase))
        undisclosed = bool(NOT_DISCLOSED.search(phrase))
        if not numbers and not negotiated and not undisclosed:
            continue
        period = _period(phrase)
        currency, currency_basis, currency_conflict = _currency(phrase, numbers)
        range_only = (len(numbers) == 2 and not phrase[:numbers[0].start()].strip()
                      and not phrase[numbers[1].end():].strip()
                      and RANGE.search(phrase[numbers[0].end():numbers[1].start()]))
        scaled_open_bound = (bool(numbers) and bool(BOUND.search(phrase)) and
                             any(re.search(r"[萬万千kK]$", n.group("amount").strip())
                                 for n in numbers))
        rate_suffix = bool(numbers and re.search(r"[/／](?:hr|hour|小時|時|月|年|日|週|周)",
                                                phrase[numbers[-1].end():], re.I))
        has_salary_context = (PAY_CUE.search(phrase) or scaled_open_bound or range_only
                             or rate_suffix or currency_basis == "EXPLICIT_TEXT")
        if not has_salary_context:
            continue
        index = len(observations)
        flags = []
        amount_min = amount_max = raw_min = raw_max = None
        if currency_basis == "PLATFORM_DEFAULT":
            flags.append("CURRENCY_DEFAULTED")
        if currency_conflict:
            flags.append("CURRENCY_CONFLICT")
        if negotiated or undisclosed:
            kind = "NEGOTIABLE" if negotiated else "NOT_DISCLOSED"
            status = kind
            if negotiated and undisclosed:
                flags.append("DISCLOSURE_TERMS_CONFLICT")
                status = "NEEDS_REVIEW"
        elif len(numbers) >= 2:
            first, second = numbers[0], numbers[1]
            between = phrase[first.end():second.start()]
            first_value, second_value = _amount(first.group("amount")), _amount(second.group("amount"))
            if RANGE.search(between) and first_value is not None and second_value is not None:
                raw_min, raw_max = first.group("amount").strip(), second.group("amount").strip()
                if first_value <= second_value:
                    amount_min, amount_max, kind = first_value, second_value, "RANGE"
                else:
                    flags.append("RANGE_ORDER_CONFLICT")
                    kind = "UNRESOLVED"
                status = "NEEDS_REVIEW" if flags else "PARSED"
            else:
                flags.append("MULTIPLE_AMOUNTS_WITHOUT_RANGE_OPERATOR")
                kind, status = "UNRESOLVED", "NEEDS_REVIEW"
        elif numbers:
            number = numbers[0]
            value = _amount(number.group("amount"))
            raw = number.group("amount").strip()
            suffix = phrase[number.end():]
            prefix = phrase[:number.start()]
            lower = bool(re.search(r"以上|起薪?|至少|最低|最少", suffix) or
                         re.search(r"最低|至少", prefix))
            upper = bool(re.search(r"以下|至多|最高|不超過|上限", suffix) or
                         re.search(r"最高|至多", prefix))
            if lower and upper:
                flags.append("BOUND_CONFLICT")
                kind, status = "UNRESOLVED", "NEEDS_REVIEW"
            elif lower:
                amount_min, raw_min, kind = value, raw, "MIN_ONLY"
                status = "PARSED" if value is not None else "NEEDS_REVIEW"
            elif upper:
                amount_max, raw_max, kind = value, raw, "MAX_ONLY"
                status = "PARSED" if value is not None else "NEEDS_REVIEW"
            else:
                amount_min, raw_min, kind = value, raw, "MIN_ONLY"
                status = "PARSED" if value is not None else "NEEDS_REVIEW"
        else:
            kind = "NEGOTIABLE" if negotiated else "NOT_DISCLOSED"
            status = kind

        if period == "UNKNOWN":
            flags.append("PAY_PERIOD_UNKNOWN")
        review_flags = {"DISCLOSURE_TERMS_CONFLICT", "RANGE_ORDER_CONFLICT",
                        "MULTIPLE_AMOUNTS_WITHOUT_RANGE_OPERATOR", "BOUND_CONFLICT",
                        "CURRENCY_CONFLICT", "PAY_PERIOD_UNKNOWN"}
        if review_flags.intersection(flags) and status == "PARSED":
            status = "NEEDS_REVIEW"
        confidence = Decimal("0.95") if status == "PARSED" else Decimal("0.60")
        if status in ("NEGOTIABLE", "NOT_DISCLOSED"):
            confidence = Decimal("0.90")
        observations.append({
            "source_kind": "DESCRIPTION", "observation_index": index,
            "raw_value_min": raw_min, "raw_value_max": raw_max,
            "amount_min": amount_min, "amount_max": amount_max,
            "currency_code": currency, "currency_basis": currency_basis,
            "pay_period": period, "range_kind": kind,
            "compensation_component": _component(phrase),
            "evidence_text": phrase, "evidence_start": start + left,
            "evidence_end": start + left + len(phrase),
            "parse_status": status, "quality_flags": flags,
            "confidence": confidence, "parser_version": PARSER_VERSION,
        })
    return observations


def _api_observation(raw_low, raw_high):
    flags = ["API_PAY_PERIOD_UNVERIFIED", "CURRENCY_DEFAULTED"]
    sentinel = False
    for value in (raw_low, raw_high):
        try:
            sentinel |= Decimal(str(value)) in (Decimal(0), Decimal(9999999))
        except (InvalidOperation, TypeError):
            if value is not None:
                flags.append("API_VALUE_UNPARSEABLE")
    status = "SENTINEL_CANDIDATE" if sentinel else "API_UNIT_UNMAPPED"
    if sentinel:
        flags.append("POSSIBLE_SENTINEL_VALUE")
    return {
        "source_kind": "API_FIELDS", "observation_index": 0,
        "raw_value_min": None if raw_low is None else str(raw_low),
        "raw_value_max": None if raw_high is None else str(raw_high),
        "amount_min": None, "amount_max": None, "currency_code": "TWD",
        "currency_basis": "PLATFORM_DEFAULT", "pay_period": "UNKNOWN",
        "range_kind": "UNRESOLVED", "compensation_component": "UNKNOWN",
        "evidence_text": None, "evidence_start": None, "evidence_end": None,
        "parse_status": status, "quality_flags": flags,
        "confidence": Decimal("1.00"), "parser_version": PARSER_VERSION,
    }


def extract_salary_observations(raw_low, raw_high, description):
    """Return one raw API observation plus any salary-bearing text clauses."""
    return [_api_observation(raw_low, raw_high), *_description_observations(description)]
