## Min transfers

Implement `min_transfers` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, backtracking, bit manipulation, dp.

## Your function

Write `min_transfers` in `solution.py`.

```python
def min_transfers(transactions: list[list[int]]) -> int
```

## Examples

**Example 1.** `min_transfers(transactions = [[0, 1, 1], [1, 2, 2], [2, 0, 1]])` returns `1`.

**Example 2.** `min_transfers(transactions = [[1, 2, 3], [2, 3, 4], [3, 1, 5]])` returns `2`.

Run checks the visible examples; Submit also runs hidden cases.
