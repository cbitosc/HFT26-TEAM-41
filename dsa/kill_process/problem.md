## Kill process

Implement `kill_process` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, graphs bfs dfs, hashing, trees.

## Your function

Write `kill_process` in `solution.py`.

```python
def kill_process(pid: list[int], ppid: list[int], kill: int) -> list[int]
```

## Examples

**Example 1.** `kill_process(pid = [1, 2, 3, 4, 5], ppid = [0, 1, 1, 2, 2], kill = 2)` returns `[2, 4, 5]`.

**Example 2.** `kill_process(pid = [1, 2, 3, 4, 5], ppid = [0, 1, 1, 2, 2], kill = 1)` returns `[1, 2, 4, 5, 3]`.

The returned list may be in any order.

Run checks the visible examples; Submit also runs hidden cases.
