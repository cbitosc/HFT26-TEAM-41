## Num islands2

Implement `num_islands2` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, hashing, union find.

## Your function

Write `num_islands2` in `solution.py`.

```python
def num_islands2(m: int, n: int, positions: list[list[int]]) -> list[int]
```

## Examples

**Example 1.** `num_islands2(m = 2, n = 2, positions = [[0, 0], [1, 1], [0, 1], [1, 0]])` returns `[1, 2, 1, 1]`.

**Example 2.** `num_islands2(m = 3, n = 3, positions = [[0, 0], [0, 1], [1, 0], [1, 1]])` returns `[1, 1, 1, 1]`.

Run checks the visible examples; Submit also runs hidden cases.
