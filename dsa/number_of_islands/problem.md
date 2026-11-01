## Num islands

Implement `num_islands` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, graphs bfs dfs, union find.

## Your function

Write `num_islands` in `solution.py`.

```python
def num_islands(grid: list[list[str]]) -> int
```

## Examples

**Example 1.** `num_islands(grid = [["1", "1", "1", "1", "0"], ["1", "1", "0", "1", "0"], ["1", "1", "0", "0", "0"], ["0", "0", "0", "0", "0"]])` returns `1`.

**Example 2.** `num_islands(grid = [["0", "0", "0", "0", "0"], ["0", "0", "0", "0", "0"], ["0", "0", "0", "0", "0"], ["0", "0", "0", "0", "0"]])` returns `0`.

Run checks the visible examples; Submit also runs hidden cases.
