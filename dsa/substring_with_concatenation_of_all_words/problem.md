## Find substring

Implement `find_substring` so that it returns the expected result for every input. The examples below show the exact input and output format; the hidden cases use more inputs of the same shape, including edge cases.

Topics: hashing, sliding window, strings.

## Your function

Write `find_substring` in `solution.py`.

```python
def find_substring(s: str, words: list[str]) -> list[int]
```

## Examples

**Example 1.** `find_substring(s = "a", words = ["a", "a", "a"])` returns `[]`.

**Example 2.** `find_substring(s = "barfoothefoobarman", words = ["foo", "bar"])` returns `[0, 9]`.

The returned list may be in any order.

Run checks the visible examples; Submit also runs hidden cases.
