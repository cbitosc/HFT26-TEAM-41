## Calc equation

Implement `calc_equation` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, graphs bfs dfs, shortest paths, strings, union find.

## Your function

Write `calc_equation` in `solution.py`.

```python
def calc_equation(equations: list[list[str]], values: list[float], queries: list[list[str]]) -> list[float]
```

## Examples

**Example 1.** `calc_equation(equations = [["a", "b"], ["b", "c"]], values = [2.0, 3.0], queries = [["a", "c"], ["b", "a"], ["a", "e"], ["a", "a"], ["x", "x"]])` returns `[6.0, 0.5, -1, 1.0, -1]`.

**Example 2.** `calc_equation(equations = [["a", "b"]], values = [0.5], queries = [["a", "b"], ["b", "a"], ["a", "c"], ["x", "y"]])` returns `[0.5, 2.0, -1, -1]`.

Answers within 1e-05 of the expected value count.

Run checks the visible examples; Submit also runs hidden cases.
