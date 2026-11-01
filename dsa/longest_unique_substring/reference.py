def length_of_longest_substring(s: str) -> int:
    """Length of the longest contiguous substring of `s` with no repeated character.

    Sliding window: `start` is the left edge of the current window; on a repeat, move it
    just past the previous occurrence of that character.
    """
    last_seen: dict[str, int] = {}
    start = best = 0
    for i, char in enumerate(s):
        if last_seen.get(char, -1) >= start:
            start = last_seen[char] + 1
        last_seen[char] = i
        best = max(best, i - start + 1)
    return best
