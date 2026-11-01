"""Generate Pydantic v2 models in contracts_gen/ from ../contracts/*.schema.json.

Run through `make contracts`. The output is committed; never edit it by hand.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = BACKEND_DIR.parent / "contracts"
OUT_DIR = BACKEND_DIR / "contracts_gen"

CODEGEN_OPTIONS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.11",
    "--use-standard-collections",
    "--use-union-operator",
    "--field-constraints",
    "--collapse-root-models",
    "--enum-field-as-literal", "all",
    "--use-schema-description",
    "--use-field-description",
    "--use-double-quotes",
    "--disable-timestamp",
    "--formatters", "builtin",
    # Keep uri/email as plain str: no URL normalisation, no email-validator dependency.
    "--type-mappings", "string+uri=string", "string+email=string",
]  # fmt: skip


def main() -> None:
    schemas = sorted(CONTRACTS_DIR.glob("*.schema.json"))
    if not schemas:
        sys.exit(f"No schemas found in {CONTRACTS_DIR}")

    # Start clean so a deleted schema doesn't leave a stale module behind.
    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("*.py"):
        old.unlink()
    (OUT_DIR / "__init__.py").write_text(
        '"""Generated from contracts/*.schema.json by `make contracts`. Do not edit."""\n'
    )

    for schema in schemas:
        module = schema.name.removesuffix(".schema.json")
        output = OUT_DIR / f"{module}.py"
        command = ["datamodel-codegen", "--input", str(schema), "--output", str(output)]
        subprocess.run([*command, *CODEGEN_OPTIONS], check=True)
        print(f"{schema.name} -> contracts_gen/{output.name}")


if __name__ == "__main__":
    main()
