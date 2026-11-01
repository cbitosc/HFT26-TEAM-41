"""Suspicious-code scan (anti-tampering rule 4d): flags only, never blocks."""

import pytest

from app.integrity import scan


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("import _pytest.runner\n", "pytest_internals"),
        ("import sys\nsys.modules['app'] = None\n", "sys_modules"),
        ("import os\nos._exit(0)\n", "os_exit"),
        ("import sys\nsys.exit(0)\n", "module_level_exit"),
        ("exit()\n", "module_level_exit"),
        ("import builtins\nbuiltins.open = None\n", "builtins_patching"),
        ("__builtins__['len'] = lambda x: 0\n", "builtins_patching"),
        ("import importlib\nimportlib.reload(x)\n", "importlib_tricks"),
        ("m = __import__('os')\n", "importlib_tricks"),
        ("open('/tmp/report.json', 'w').write('{}')\n", "write_outside_workspace"),
        (
            "from pathlib import Path\nPath('/runner-out/x').write_text('1')\n",
            "write_outside_workspace",
        ),
    ],
)
def test_each_rule_is_flagged(code: str, rule: str) -> None:
    flags = scan({"app/calc.py": code})
    assert rule in {flag.rule for flag in flags}
    assert all(flag.path == "app/calc.py" and flag.line >= 1 for flag in flags)


@pytest.mark.parametrize(
    ("path", "code", "rule"),
    [
        ("src/sum.js", "process.exit(0);\n", "process_exit"),
        ("src/sum.js", "delete require.cache[k];\n", "importlib_tricks"),
        ("src/sum.js", "fs.writeFileSync('/tmp/x', 'y');\n", "write_outside_workspace"),
    ],
)
def test_node_rules(path: str, code: str, rule: str) -> None:
    assert rule in {flag.rule for flag in scan({path: code})}


def test_innocent_code_is_not_flagged() -> None:
    code = (
        "import sys\n\n"
        "def main():\n"
        "    sys.exit(main_inner())\n\n"  # inside a function: not at import time
        "with open('/workspace/out.txt', 'w') as f:\n"
        "    f.write('ok')\n"
        "path = '/etc/hosts'  # read, not written\n"
    )
    assert scan({"app/cli.py": code}) == []


def test_flag_records_line_and_excerpt() -> None:
    flags = scan({"app/calc.py": "x = 1\nimport _pytest\n"})
    assert [(f.line, f.excerpt) for f in flags] == [(2, "import _pytest")]
