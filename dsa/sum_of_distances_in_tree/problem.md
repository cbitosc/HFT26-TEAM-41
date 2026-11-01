## Sum of distances in tree

Implement `sum_of_distances_in_tree` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: dp, graphs bfs dfs, trees.

## Your function

Write `sum_of_distances_in_tree` in `solution.py`.

```python
def sum_of_distances_in_tree(n: int, edges: list[list[int]]) -> list[int]
```

## Examples

**Example 1.** `sum_of_distances_in_tree(n = 4, edges = [[0, 1], [1, 2], [1, 3]])` returns `[5, 3, 5, 5]`.

**Example 2.** `sum_of_distances_in_tree(n = 4, edges = [[0, 1], [0, 2], [1, 3]])` returns `[4, 4, 6, 6]`.

Run checks the visible examples; Submit also runs hidden cases.
