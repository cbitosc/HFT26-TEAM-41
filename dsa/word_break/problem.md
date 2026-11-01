## Word break

Implement `word_break` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, dp, hashing, strings, tries.

## Your function

Write `word_break` in `solution.py`.

```python
def word_break(s: str, wordDict: list[str]) -> bool
```

## Examples

**Example 1.** `word_break(s = "cars", wordDict = ["car", "ca", "rs"])` returns `True`.

**Example 2.** `word_break(s = "goals", wordDict = ["go", "goal", "goals"])` returns `True`.

Run checks the visible examples; Submit also runs hidden cases.
