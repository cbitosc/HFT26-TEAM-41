## K smallest pairs

Implement `k_smallest_pairs` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, heaps.

## Your function

Write `k_smallest_pairs` in `solution.py`.

```python
def k_smallest_pairs(nums1: list[int], nums2: list[int], k: int) -> list[list[int]]
```

## Examples

**Example 1.** `k_smallest_pairs(nums1 = [1, 2], nums2 = [3], k = 3)` returns `[[1, 3], [2, 3]]`.

**Example 2.** `k_smallest_pairs(nums1 = [1, 7, 11], nums2 = [2, 4, 6], k = 3)` returns `[[1, 2], [1, 4], [1, 6]]`.

Run checks the visible examples; Submit also runs hidden cases.
