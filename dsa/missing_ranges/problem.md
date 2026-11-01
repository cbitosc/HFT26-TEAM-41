## Find missing ranges

Implement `find_missing_ranges` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays.

## Your function

Write `find_missing_ranges` in `solution.py`.

```python
def find_missing_ranges(nums: list[int], lower: int, upper: int) -> list[list[int]]
```

## Examples

**Example 1.** `find_missing_ranges(nums = [], lower = 1, upper = 1)` returns `[[1, 1]]`.

**Example 2.** `find_missing_ranges(nums = [], lower = -3, upper = 3)` returns `[[-3, 3]]`.

Run checks the visible examples; Submit also runs hidden cases.
