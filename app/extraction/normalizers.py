import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable

from app.schemas.extraction import NormalizedValue


@dataclass(frozen=True)
class NormalizedResult:
    value: NormalizedValue
    unit: str | None = None


Normalizer = Callable[[str], NormalizedResult | None]


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip(" \t\r\n:：;；,，")


def normalize_string(raw: str) -> NormalizedResult | None:
    value = _clean(raw)
    if not value or len(value) > 240:
        return None
    return NormalizedResult(value)


def normalize_identifier(raw: str) -> NormalizedResult | None:
    value = _clean(raw)
    value = re.sub(r"\s*([./_\-+])\s*", r"\1", value)
    if not value or len(value) > 120:
        return None
    return NormalizedResult(value)


def _number(raw: str) -> Decimal | None:
    raw = unicodedata.normalize("NFKC", raw)
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        value = Decimal(match.group(0).replace(",", ""))
        if abs(value) > Decimal("1e15"):
            return None
        return value
    except InvalidOperation:
        return None


def _compact_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value.quantize(Decimal("0.000001")).normalize())


def normalize_integer(raw: str) -> NormalizedResult | None:
    value = _number(raw)
    if value is None or value != value.to_integral_value():
        return None
    return NormalizedResult(int(value))


def normalize_power_w(raw: str) -> NormalizedResult | None:
    value = _number(raw)
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", raw).casefold()
    if "mw" in text or "兆瓦" in text:
        value *= Decimal("1000000")
    elif "kw" in text or "千瓦" in text:
        value *= Decimal("1000")
    elif "w" not in text and "瓦" not in text:
        return None
    return NormalizedResult(_compact_number(value), "W")


def normalize_capacity_kw(raw: str) -> NormalizedResult | None:
    value = _number(raw)
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", raw).casefold()
    if "mw" in text or "兆瓦" in text:
        value *= Decimal("1000")
    elif "kw" in text or "千瓦" in text:
        pass
    elif "w" in text or "瓦" in text:
        value /= Decimal("1000")
    else:
        return None
    return NormalizedResult(_compact_number(value), "kW")


def normalize_money_cny(raw: str) -> NormalizedResult | None:
    raw = unicodedata.normalize("NFKC", raw)
    value = _number(raw)
    if value is None:
        return None
    if "亿元" in raw:
        value *= Decimal("100000000")
    elif "万元" in raw:
        value *= Decimal("10000")
    return NormalizedResult(_compact_number(value), "CNY")


def normalize_date(raw: str) -> NormalizedResult | None:
    raw = unicodedata.normalize("NFKC", raw)
    match = re.search(r"(\d{4})[年./\-](\d{1,2})[月./\-](\d{1,2})日?", raw)
    if not match:
        return None
    try:
        parsed = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    return NormalizedResult(parsed.isoformat())


NORMALIZERS: dict[str, Normalizer] = {
    "string": normalize_string,
    "identifier": normalize_identifier,
    "integer": normalize_integer,
    "power_w": normalize_power_w,
    "capacity_kw": normalize_capacity_kw,
    "money_cny": normalize_money_cny,
    "date": normalize_date,
    "conclusion": normalize_string,
}
