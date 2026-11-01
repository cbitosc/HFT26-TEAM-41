## Longest run of distinct characters

Implement `length_of_longest_substring(s)` in `solution.py`.

Given a string `s`, return the length of the longest contiguous piece of `s` in which no
character appears more than once. Characters are compared exactly (upper and lower case
differ, and spaces and digits count as characters). An empty string gives `0`.

| `s` | Result | Why |
| --- | --- | --- |
| `"abcabcbb"` | `3` | `"abc"` |
| `"bbbbb"` | `1` | `"b"` |
| `"pwwkew"` | `3` | `"wke"`; `"pwke"` is not contiguous |

Inputs can be up to a few thousand characters long, so aim for a single pass over `s`.
