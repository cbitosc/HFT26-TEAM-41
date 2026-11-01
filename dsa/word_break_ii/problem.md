## Word break

Implement `word_break` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: arrays, backtracking, dp, hashing, strings, tries.

## Your function

Write `word_break` in `solution.py`.

```python
def word_break(s: str, wordDict: list[str]) -> list[str]
```

## Examples

**Example 1.** `word_break(s = "aaaaaaa", wordDict = ["aa", "aaa"])` returns `["aa aa aaa", "aa aaa aa", "aaa aa aa"]`.

**Example 2.** `word_break(s = "a", wordDict = ["a"])` returns `["a"]`.

The returned list may be in any order.

Run checks the visible examples; Submit also runs hidden cases.
