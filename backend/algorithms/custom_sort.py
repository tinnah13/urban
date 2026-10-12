
"""
Custom Merge Sort + Top-K Heap
==============================

PROBLEM: Rank top-N zones by trip count WITHOUT using Python's built-in
sorted(), list.sort(), heapq, or pandas sort_values().

APPROACH: Two-stage algorithm
  1. Build a size-K min-heap while scanning the data — O(n log K)
  2. Extract heap elements and sort with custom merge sort — O(K log K)
  3. Total: O(n log K) time, O(K) space

WHY NOT FULL SORT?
  Full sort is O(n log n). When K << n (e.g., top 10 of 100,000), the
  heap approach is dramatically faster because we never sort the whole list.

WHY MERGE SORT?
  - Stable (preserves insertion order for ties)
  - Guaranteed O(n log n) — no worst-case degradation like quicksort
  - Easier to reason about for a report/paper
"""
# =============================================================================
# Implementation Notes
# ============================================================================
# this module implements merge sort from first principles to satisfy the
# assignment's requirment of no built-in sorting functions.
#
# Why merge sort?
#   - stable: ties preserve original order, which matters when chaining multiple sort criteria.
#   - predictable: 0(n log n) in best, average, and worst cases.
#   - parallelizable: left and right halves can sort independently.
#
# Why NOT quicksort?
#   - wost case 0(n^2) on already-sorted input.
#   - Not stable without extra bookkeeping.
#
# Why the bounded heap for top-k?
#   - When K<< n, a full sort wastes work. We only need the K largest.
#   - Time drops from 0(n log n) to 0(n log k).
#   - Space drops from 0(n) to 0(k).
# ============================================================================
# Custom merge sort + bounded heap



from typing import List, Dict, Any


# ============================================================================
# MERGE SORT
# ============================================================================
def custom_merge_sort(arr: List[Dict], key: str, reverse: bool = False) -> List[Dict]:
    """
    Sort a list of dictionaries by the specified key using merge sort.

    Args:
        arr:     list of dicts to sort
        key:     dict key to sort on (numeric)
        reverse: True for descending

    Returns:
        New sorted list

    Time:  O(n log n)
    Space: O(n)  — for the temporary merged arrays
    """
    if len(arr) <= 1:
        return list(arr)

    mid = len(arr) // 2
    left = custom_merge_sort(arr[:mid], key, reverse)
    right = custom_merge_sort(arr[mid:], key, reverse)
    return _merge(left, right, key, reverse)


def _merge(left: List[Dict], right: List[Dict], key: str, reverse: bool) -> List[Dict]:
    """Merge two sorted lists preserving the sort direction."""
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        lv = left[i].get(key, 0) or 0
        rv = right[j].get(key, 0) or 0

        take_left = (lv >= rv) if reverse else (lv <= rv)
        if take_left:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    # Append remaining
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# ============================================================================
# MIN-HEAP (used for top-K selection)
# ============================================================================
def _heap_push(heap: List[tuple], item: tuple, reverse: bool) -> None:
    """Push onto heap and bubble up."""
    heap.append(item)
    idx = len(heap) - 1
    while idx > 0:
        parent = (idx - 1) // 2
        # reverse=True means "top-K largest" → we keep a MIN-heap
        # reverse=False means "top-K smallest" → we keep a MAX-heap
        if reverse:
            if heap[idx][0] < heap[parent][0]:
                heap[idx], heap[parent] = heap[parent], heap[idx]
                idx = parent
            else:
                break
        else:
            if heap[idx][0] > heap[parent][0]:
                heap[idx], heap[parent] = heap[parent], heap[idx]
                idx = parent
            else:
                break


def _heap_pop(heap: List[tuple]) -> tuple:
    """Pop root and re-heapify."""
    if not heap:
        return None
    root = heap[0]
    last = heap.pop()
    if heap:
        heap[0] = last
        _sift_down(heap, 0)
    return root


def _sift_down(heap: List[tuple], idx: int) -> None:
    n = len(heap)
    while True:
        smallest = idx
        l = 2 * idx + 1
        r = 2 * idx + 2
        if l < n and heap[l][0] < heap[smallest][0]:
            smallest = l
        if r < n and heap[r][0] < heap[smallest][0]:
            smallest = r
        if smallest == idx:
            break
        heap[idx], heap[smallest] = heap[smallest], heap[idx]
        idx = smallest


# ============================================================================
# TOP-K
# ============================================================================
def get_top_k_trips(trips: List[Dict], key: str, k: int, reverse: bool = True) -> List[Dict]:
    """
    Return top-K trips by key.

    Uses a bounded heap of size K so we never allocate more than K items.

    Time:  O(n log K)
    Space: O(K)
    """
    if k <= 0:
        return []
    if len(trips) <= k:
        return custom_merge_sort(trips, key, reverse)

    heap: List[tuple] = []

    for item in trips:
        val = item.get(key, 0) or 0
        if len(heap) < k:
            _heap_push(heap, (val, item), reverse)
        else:
            # Compare with heap root
            root_val = heap[0][0]
            if reverse:
                # top-K largest: replace root if item > root
                if val > root_val:
                    _heap_pop(heap)
                    _heap_push(heap, (val, item), reverse)
            else:
                # top-K smallest: replace root if item < root
                if val < root_val:
                    _heap_pop(heap)
                    _heap_push(heap, (val, item), reverse)

    # Extract trips, then custom-sort the K results for final ordering
    extracted = [t for (_, t) in heap]
    return custom_merge_sort(extracted, key, reverse)


# ============================================================================
# COMPLEXITY SUMMARY (for the report)
# ============================================================================
"""
Merge Sort:
  T(n) = 2·T(n/2) + O(n)
  Master theorem case 2 → T(n) = O(n log n)
  Space = O(n) (merge buffers)

Top-K with bounded heap:
  Insertion: O(log K) per element
  Total:     O(n log K)
  Space:     O(K)

Full sort (comparison baseline):
  O(n log n) time, O(n) space

For 265 zones and K=10:
  Full sort = 265 · log(265)      ≈ 2,130 operations
  Top-K     = 265 · log(10)       ≈   880 operations
  → ~60% fewer comparisons
"""

def describe_algorithm():
    """
    Returns a short human- readable description of the algorithm.
    used by the API's  /api/alorithm-info endpoints.
    """
    return {
        "name": "merge_sort_with_bounded_heap",
        "time": "0(n log K)",
        "space": "0(K)",
        "stable": True,
        "library_free": True,
    }