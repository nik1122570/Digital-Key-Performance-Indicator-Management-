"""Framework-independent rules. Decimal arithmetic is deliberate; no float scoring."""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP

INDICATORS = ("Percentage", "Number", "Currency", "Duration", "Yes No", "Date", "Text")
NUMERIC = INDICATORS[:4]
UNITS = ("Hours", "Days", "Weeks", "Months", "Years")
FREQUENCIES = {"Monthly": 1, "Quarterly": 3, "Semi-Annual": 6}
CENT = Decimal("0.01")


def decimal(value, places=None):
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError("A numeric value is required (zero is valid)")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid number") from None
    if not result.is_finite():
        raise ValueError("Numbers must be finite")
    if abs(result) > Decimal("999999999999.999999"):
        raise ValueError("Number exceeds the supported storage range")
    if places is not None and result != result.quantize(Decimal(1).scaleb(-places)):
        raise ValueError(f"Use at most {places} decimal places")
    return result


def day(value):
    if isinstance(value, date):
        return date(value.year, value.month, value.day)
    return date.fromisoformat(str(value)[:10])


def period_containing(value, frequency):
    d = day(value)
    months = FREQUENCIES[frequency]
    month = (d.month - 1) // months * months + 1
    end_month = month + months - 1
    start = date(d.year, month, 1)
    end = date(d.year, end_month, monthrange(d.year, end_month)[1])
    key = (
        f"{d.year}-{month:02}"
        if months == 1
        else f"{d.year}-{'Q' if months == 3 else 'H'}{(month - 1) // months + 1}"
    )
    return start, end, key


def periods(start, end, frequency, closed_before=None, not_before=None):
    start, end = day(start), day(end)
    if start > end:
        raise ValueError("Start date must not follow end date")
    cursor = start
    while cursor <= end:
        pstart, pend, key = period_containing(cursor, frequency)
        if (
            pstart >= start
            and pend <= end
            and (closed_before is None or pend < day(closed_before))
            and (not_before is None or pstart >= day(not_before))
        ):
            yield pstart, pend, key
        if pend.year == 9999 and pend.month == 12:
            break
        cursor = date(pend.year + (pend.month == 12), pend.month % 12 + 1, 1)


def eligible(assignment, structure, start, end, today):
    start, end = day(start), day(end)
    canonical_start, canonical_end, key = period_containing(
        start, assignment["review_frequency"]
    )
    if (start, end) != (canonical_start, canonical_end):
        raise ValueError("The review must cover one complete calendar period")
    if assignment["docstatus"] != 1 or structure["docstatus"] != 1:
        raise ValueError("Assignment and Structure must both be submitted")
    if not (
        day(assignment["start_date"]) <= start <= end <= day(assignment["end_date"])
    ):
        raise ValueError("The assignment must cover the complete review period")
    if start < day(structure["effective_from"]) or (
        structure.get("effective_to") and end > day(structure["effective_to"])
    ):
        raise ValueError("The Structure must cover the complete review period")
    if end >= day(today):
        raise ValueError("The review period has not closed")
    return key


def typed_value(row, prefix, require=True):
    indicator = row.get("indicator")
    if indicator not in INDICATORS:
        raise ValueError("Select a valid indicator")
    if indicator != "Duration" and row.get("duration_unit"):
        raise ValueError("Duration unit is only valid for a Duration indicator")
    if indicator != "Currency" and row.get("currency"):
        raise ValueError("Currency is only valid for a Currency indicator")
    operative = (
        "number"
        if indicator in NUMERIC
        else {"Yes No": "choice", "Date": "date", "Text": "text"}[indicator]
    )
    for suffix in ("number", "choice", "date", "text"):
        v = row.get(f"{prefix}_{suffix}")
        if suffix != operative and v not in (None, "", 0, 0.0):
            raise ValueError(f"Unexpected {prefix} value for {indicator}")
    value = row.get(f"{prefix}_{operative}")
    if not require and value in (None, ""):
        return None
    if operative == "number":
        value = decimal(value, 6)
        if indicator == "Duration" and (
            value < 0 or row.get("duration_unit") not in UNITS
        ):
            raise ValueError("Duration requires a nonnegative value and a valid unit")
        if indicator == "Currency" and not row.get("currency"):
            raise ValueError("Currency is required")
    elif operative == "choice":
        if value not in ("Yes", "No"):
            raise ValueError("Choose Yes or No")
    elif operative == "date":
        value = day(value)
    elif value is None or not str(value).strip():
        raise ValueError("Text must not be blank")
    return value


def display_value(row, prefix):
    value = typed_value(row, prefix)
    if isinstance(value, Decimal):
        value = format(value.normalize(), "f")
    indicator = row["indicator"]
    suffix = {
        "Percentage": "%",
        "Currency": " " + (row.get("currency") or ""),
        "Duration": " " + (row.get("duration_unit") or ""),
    }.get(indicator, "")
    return str(value) + suffix


def validate_weights(rows):
    if not rows:
        raise ValueError("At least one KPI component is required")
    weights = [decimal(r.get("weight", r.get("original_weight")), 2) for r in rows]
    if any(w <= 0 or w > 100 for w in weights) or sum(weights) != 100:
        raise ValueError("Positive component weights must total exactly 100.00")
    components = [r["kpi_component"] for r in rows]
    if len(set(components)) != len(components):
        raise ValueError("A component may appear only once")


def normalized_weights(rows):
    weights = [decimal(r["original_weight"], 2) for r in rows]
    if any(w <= 0 for w in weights):
        raise ValueError("Original weights must be positive")
    active = [i for i, r in enumerate(rows) if not r.get("not_applicable")]
    denominator = sum((weights[i] for i in active), Decimal(0))
    result = [Decimal(0) for _ in rows]
    if not denominator:
        return result
    exact = {i: 100 * weights[i] / denominator for i in active}
    for i in active:
        result[i] = exact[i].quantize(CENT, rounding=ROUND_DOWN)
    remainder = int((100 - sum(result)) * 100)
    order = sorted(
        active,
        key=lambda i: (
            -(exact[i] - result[i]),
            rows[i].get("idx", i + 1),
            rows[i].get("structure_item_id", ""),
        ),
    )
    for i in order[:remainder]:
        result[i] += CENT
    return result


def valid_rating(value, original_weight):
    score = decimal(value, 2)
    if not 0 <= score <= decimal(original_weight, 2):
        raise ValueError("Rating must be between zero and the original weight")
    return score


def calculate(rows):
    effective = normalized_weights(rows)
    active = [i for i, r in enumerate(rows) if not r.get("not_applicable")]
    result = []
    for row, weight in zip(rows, effective):
        out = {"effective_weight": weight}
        for stage in ("self", "final"):
            score = valid_rating(row.get(f"{stage}_rating", 0), row["original_weight"])
            out[f"{stage}_points"] = (
                (weight * score / decimal(row["original_weight"])).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                if row.get(f"{stage}_rating_entered")
                else Decimal(0)
            )
        out["rating_variance"] = out["final_points"] - out["self_points"]
        result.append(out)
    totals = {
        "applicable_weight": sum(
            (decimal(rows[i]["original_weight"]) for i in active), Decimal(0)
        ),
        "excluded_weight": sum(
            (decimal(r["original_weight"]) for r in rows if r.get("not_applicable")),
            Decimal(0),
        ),
        "effective_weight_total": sum(effective),
    }
    for stage in ("self", "final"):
        complete = bool(active) and all(
            rows[i].get(f"{stage}_rating_entered") for i in active
        )
        totals[f"{stage}_complete"] = int(complete)
        totals[f"{stage}_total"] = (
            sum((result[i][f"{stage}_points"] for i in active), Decimal(0))
            if complete
            else None
        )
    return result, totals


def category(total):
    value = decimal(total, 2)
    if not 0 <= value <= 100:
        raise ValueError("Total must be between 0 and 100")
    for limit, label in [
        (90, "Outstanding"),
        (71, "Exceeds Expectations"),
        (60, "Meets Expectations"),
        (40, "Improvement Needed"),
        (0, "Poor"),
    ]:
        if value >= limit:
            return label

