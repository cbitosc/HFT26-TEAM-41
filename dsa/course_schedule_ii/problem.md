## Find order

Implement `find_order` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: graphs bfs dfs.

## Your function

Write `find_order` in `solution.py`.

```python
def find_order(numCourses: int, prerequisites: list[list[int]]) -> list[int]
```

## Examples

**Example 1.** `find_order(numCourses = 3, prerequisites = [[0, 1], [1, 2], [2, 0]])` returns `[]`.

**Example 2.** `find_order(numCourses = 3, prerequisites = [[1, 0], [0, 1]])` returns `[]`.

Run checks the visible examples; Submit also runs hidden cases.
