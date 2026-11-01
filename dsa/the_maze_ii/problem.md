## Shortest distance

Implement `shortest_distance` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, graphs bfs dfs, heaps, shortest paths.

## Your function

Write `shortest_distance` in `solution.py`.

```python
def shortest_distance(maze: list[list[int]], start: list[int], destination: list[int]) -> int
```

## Examples

**Example 1.** `shortest_distance(maze = [[0, 0, 1, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 1, 0], [1, 1, 0, 1, 1], [0, 0, 0, 0, 0]], start = [0, 4], destination = [4, 4])` returns `12`.

**Example 2.** `shortest_distance(maze = [[0, 0, 0, 0, 0], [1, 1, 0, 0, 1], [0, 0, 0, 0, 0], [0, 1, 0, 0, 1], [0, 1, 0, 0, 0]], start = [4, 3], destination = [0, 1])` returns `-1`.

Run checks the visible examples; Submit also runs hidden cases.
