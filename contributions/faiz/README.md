# Faiz — portfolio collectors

Public-profile and resume tools used to build a candidate portfolio for the adaptive coding assessment.

| Piece | What it does |
| --- | --- |
| `github_profile.py` | Public GitHub profile stats from a profile link |
| `leetcode_profile.py` | Public LeetCode stats from a profile link |
| `codeforces_profile.py` | Public Codeforces stats from a profile link |
| `github_repo_analysis/` | Reads a public GitHub repo and writes a skill report |
| `Resume-OCR-Parser/` | Resume parser (PDF, image, or text) into JSON |

Shared dependency for the three profile scripts: `requirements.txt` (`requests`).

The resume parser reads `GEMINI_API_KEY` from the environment. Do not commit a `.env` file.
