
"""
Custom IQR-Based Anomaly Detector
=================================

PROBLEM: Detect unusually-priced trips WITHOUT using scipy, sklearn,
numpy.percentile, or pandas quantile.

APPROACH: Tukey's Interquartile Range (IQR) method
  - Sort values with our custom merge sort
  - Compute Q1 (25th percentile) and Q3 (75th percentile)
  - Flag values outside [Q1 - 1.5·IQR, Q3 + 1.5·IQR]

WHY IQR?
  - Robust to extreme outliers (unlike mean/stddev)
  - Non-parametric (no normal-distribution assumption)
  - Easy to explain to non-technical stakeholders

COMPLEXITY:
  Time:  O(n log n) — dominated by the sort
  Space: O(n)      — sorted copy + result lists
"""
# ============================================================================
# Why IQR?
# ============================================================================
# The Interquartile Range Method is robust to extreme outliers because it
# relies on percentiles rather than mean and standard deviation.
#
# Example: if 10 fares in a batch  are $500,000 each (data entry erros),
# the mean and std-dev explode, but Q1 and Q3 barely move.
#
# Interpretation of the 1.5 * IQR threshold:
#  - 1.5x = standard "outlier" boundary (Tukry's original paper)
#  - 3.0x = "extreme outlier" boundary
# We default to 1.5x for sensitivity.
# ============================================================================
# IQR-based anomaly detector

from typing import List, Dict, Tuple


# ============================================================================
# Percentile via linear interpolation
# ============================================================================
def calculate_percentile(sorted_arr: List[float], percentile: float) -> float:
    """
    Compute percentile from a pre-sorted list using linear interpolation.

    Same method as numpy.percentile(..., interpolation='linear').
    """
    if not sorted_arr:
        return 0.0

    n = len(sorted_arr)
    rank = (percentile / 100.0) * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    frac = rank - lower

    return sorted_arr[lower] + frac * (sorted_arr[upper] - sorted_arr[lower])


# ============================================================================
# Sort numbers with custom merge sort (no sorted()/list.sort())
# ============================================================================
def _sort_numbers(arr: List[float]) -> List[float]:
    if len(arr) <= 1:
        return list(arr)
    mid = len(arr) // 2
    left = _sort_numbers(arr[:mid])
    right = _sort_numbers(arr[mid:])
    return _merge_numbers(left, right)


def _merge_numbers(left: List[float], right: List[float]) -> List[float]:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# ============================================================================
# Severity scoring
# ============================================================================
def _severity(value: float, q1: float, q3: float, iqr: float) -> str:
    if iqr == 0:
        return "unknown"
    distance = (q1 - value) / iqr if value < q1 else (value - q3) / iqr
    if distance > 3:
        return "extreme"
    if distance > 2:
        return "high"
    if distance > 1.5:
        return "moderate"
    return "low"


# ============================================================================
# Main detector
# ============================================================================
def detect_anomalies_iqr(
    trips: List[Dict],
    field: str = "total_amount",
    multiplier: float = 1.5,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Split trips into (normal, anomalies) using IQR bounds.

    Args:
        trips:      list of dicts
        field:      numeric field to analyze
        multiplier: IQR multiplier — 1.5 = standard, 3.0 = extreme

    Returns:
        (normal_trips, anomalies) — anomalies have extra metadata fields

    Time:  O(n log n)
    Space: O(n)
    """
    if not trips:
        return [], []

    values = [float(t.get(field, 0) or 0) for t in trips]
    sorted_values = _sort_numbers(values)

    q1 = calculate_percentile(sorted_values, 25)
    q3 = calculate_percentile(sorted_values, 75)
    iqr = q3 - q1

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    normal, anomalies = [], []
    for t in trips:
        val = float(t.get(field, 0) or 0)
        if lower <= val <= upper:
            normal.append(t)
        else:
            a = dict(t)
            a["anomaly_field"] = field
            a["anomaly_value"] = round(val, 2)
            a["anomaly_bounds"] = f"[{lower:.2f}, {upper:.2f}]"
            a["anomaly_severity"] = _severity(val, q1, q3, iqr)
            a["iqr_stats"] = {
                "q1": round(q1, 2),
                "q3": round(q3, 2),
                "iqr": round(iqr, 2),
            }
            anomalies.append(a)

    return normal, anomalies

def anomaly_summary(trips, field="total_amount"):
    """
    Returns a compact statistical summary of anomaly detection.
    Useful for surfacing on a dashboard badge.

    """
    normal, bad = detect_anomalies_iqr(trips, field=field)
    total = len(trips)
    return {
        "field": field,
        "total_scanned": total,
        "normal_count": len(normal),
        "anomaly_count": len(bad),
        "anomaly_rate_pct": round(100.0 * len(bad) / total, 2) if total else 0,

    }
