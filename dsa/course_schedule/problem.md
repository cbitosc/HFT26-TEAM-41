## Can finish

Implement `can_finish` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: graphs bfs dfs.

## Your function

Write `can_finish` in `solution.py`.

```python
def can_finish(numCourses: int, prerequisites: list[list[int]]) -> bool
```

## Examples

**Example 1.** `can_finish(numCourses = 2, prerequisites = [[1, 0], [0, 1]])` returns `False`.

**Example 2.** `can_finish(numCourses = 5, prerequisites = [[1, 4], [2, 4], [3, 1], [3, 2]])` returns `True`.

Run checks the visible examples; Submit also runs hidden cases.
