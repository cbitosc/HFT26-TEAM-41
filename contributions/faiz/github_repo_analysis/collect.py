"""Static evidence collection for a repository checkout."""

from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

MAX_DEEP_FILES = 2500
MAX_FILE_BYTES = 1_000_000
EXCERPT_LINES = 32

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "dist", "build", "out",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".next", ".nuxt", "coverage",
    "vendor", "target", "bin", "obj", ".gradle", ".idea", "Pods",
}
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "cargo.lock", "go.sum", "composer.lock", "gemfile.lock", "packages.lock.json",
}

EXT_LANGUAGE = {
    ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".vue": "Vue",
    ".svelte": "Svelte", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".swift": "Swift", ".scala": "Scala", ".dart": "Dart", ".r": "R", ".lua": "Lua",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "Sass",
    ".less": "Less", ".md": "Markdown", ".json": "JSON", ".yml": "YAML", ".yaml": "YAML",
    ".toml": "TOML", ".xml": "XML", ".sol": "Solidity", ".move": "Move",
    ".dockerfile": "Dockerfile", ".tf": "Terraform", ".graphql": "GraphQL",
    ".gql": "GraphQL", ".proto": "Protocol Buffers",
}
NON_PRIMARY = {
    "Markdown", "JSON", "YAML", "TOML", "XML", "Text",
}

PURPOSE = {
    "react": "Builds user interface components.",
    "react-dom": "Renders React components in the browser.",
    "vue": "Builds the user interface.",
    "angular": "Builds the user interface.",
    "@angular/core": "Angular application framework.",
    "next": "React framework with routing and server rendering.",
    "express": "HTTP server and route handling.",
    "fastify": "HTTP server.",
    "koa": "HTTP server.",
    "django": "Python web framework.",
    "flask": "Python web framework.",
    "fastapi": "Python API framework.",
    "spring-boot": "Java application framework.",
    "tensorflow": "Machine learning model training and inference.",
    "torch": "Machine learning model training and inference.",
    "pytorch": "Machine learning model training and inference.",
    "scikit-learn": "Classical machine learning.",
    "sklearn": "Classical machine learning.",
    "transformers": "Pretrained transformer models.",
    "opencv-python": "Image processing.",
    "cv2": "Image processing.",
    "mediapipe": "Perception pipelines such as vision tasks.",
    "axios": "HTTP client.",
    "redux": "Client state container.",
    "@reduxjs/toolkit": "Client state container.",
    "zustand": "Client state container.",
    "pinia": "Vue state container.",
    "vue-router": "Vue page routing.",
    "react-router-dom": "React page routing.",
    "tailwindcss": "Utility CSS styling.",
    "bootstrap": "CSS component styling.",
    "mui": "React component library.",
    "@mui/material": "React component library.",
    "antd": "React component library.",
    "formik": "Form state and validation.",
    "react-hook-form": "Form state.",
    "zod": "Schema validation.",
    "yup": "Schema validation.",
    "joi": "Schema validation.",
    "pydantic": "Data validation.",
    "sqlalchemy": "SQL database access.",
    "prisma": "Database client and schema.",
    "@prisma/client": "Database client.",
    "mongoose": "MongoDB object modeling.",
    "sequelize": "SQL object modeling.",
    "typeorm": "SQL object modeling.",
    "pg": "PostgreSQL driver.",
    "psycopg2": "PostgreSQL driver.",
    "psycopg": "PostgreSQL driver.",
    "pymysql": "MySQL driver.",
    "mysql2": "MySQL driver.",
    "redis": "In-memory store, often used as a cache.",
    "ioredis": "Redis client.",
    "firebase": "Firebase client.",
    "firebase-admin": "Firebase server SDK.",
    "boto3": "AWS SDK.",
    "aws-sdk": "AWS SDK.",
    "@aws-sdk/client-s3": "AWS S3 client.",
    "jsonwebtoken": "JWT creation and checks.",
    "pyjwt": "JWT creation and checks.",
    "bcrypt": "Password hashing.",
    "bcryptjs": "Password hashing.",
    "passlib": "Password hashing.",
    "passport": "Authentication middleware.",
    "cors": "Cross-origin request policy.",
    "helmet": "HTTP security headers.",
    "multer": "Multipart file uploads.",
    "celery": "Background tasks.",
    "bull": "Background jobs.",
    "socket.io": "WebSocket communication.",
    "pytest": "Python tests.",
    "jest": "JavaScript tests.",
    "mocha": "JavaScript tests.",
    "vitest": "JavaScript tests.",
    "junit": "Java tests.",
    "webpack": "JavaScript bundling.",
    "vite": "Frontend build tool.",
    "eslint": "JavaScript linting.",
    "prettier": "Source formatting.",
    "docker": "Container image definition when a Dockerfile is present.",
    "gunicorn": "Python WSGI server.",
    "uvicorn": "Python ASGI server.",
    "hibernate": "Java ORM.",
}

FRONTEND_NAMES = {
    "react", "react-dom", "vue", "angular", "@angular/core", "next", "nuxt",
    "svelte", "tailwindcss", "bootstrap", "@mui/material", "mui", "antd",
    "redux", "@reduxjs/toolkit", "zustand", "pinia", "vuex", "mobx",
    "react-router-dom", "vue-router", "@angular/router", "formik",
    "react-hook-form", "axios", "styled-components", "sass",
}
BACKEND_NAMES = {
    "express", "fastify", "koa", "django", "flask", "fastapi", "spring-boot",
    "nestjs", "@nestjs/core", "gin", "echo", "rails", "laravel", "actix-web",
    "uvicorn", "gunicorn", "hapi",
}
DB_NAMES = {
    "prisma", "@prisma/client", "mongoose", "sequelize", "typeorm", "sqlalchemy",
    "pg", "psycopg2", "psycopg", "pymysql", "mysql2", "sqlite3", "mongodb",
    "pymongo", "redis", "ioredis", "firebase", "firebase-admin", "motor",
    "knex", "drizzle-orm",
}
ML_NAMES = {
    "tensorflow", "torch", "pytorch", "scikit-learn", "sklearn", "keras",
    "transformers", "opencv-python", "cv2", "mediapipe", "xgboost", "lightgbm",
    "nltk", "spacy", "datasets", "huggingface-hub",
}

SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-")),
    ("Assigned secret", re.compile(
        r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    )),
]
PLACEHOLDER = re.compile(
    r"(?i)(your[_-]?|example|changeme|placeholder|todo|process\.env|os\.environ|os\.getenv|"
    r"xxxx+|<.*>|\$\{|insert|dummy|sample|redacted|none|null|undefined)"
)

ROUTE_PATTERNS = [
    re.compile(r"@(?:app|router|bp|blueprint)\.(?:route|get|post|put|patch|delete|api_route)\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\.(?:get|post|put|patch|delete|put|options|head)\(\s*['\"](/[^'\"]*)['\"]", re.I),
    re.compile(r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)['\"]"),
    re.compile(r"\bpath\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"@(?:app|router)\.(?:websocket|ws)\(\s*['\"]([^'\"]+)['\"]", re.I),
]
URL_PATTERN = re.compile(r"https?://[^\s'\"<>)\\]+")
SKIP_HOSTS = ("schema.org", "www.w3.org", "json-schema.org", "example.com", "localhost", "127.0.0.1")


def redact(text: str) -> str:
    text = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED-PRIVATE-KEY]", text)
    text = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED-AWS-KEY]", text)
    text = re.sub(r"ghp_[A-Za-z0-9]{20,}", "[REDACTED-TOKEN]", text)
    text = re.sub(r"xox[baprs]-[A-Za-z0-9-]+", "[REDACTED-TOKEN]", text)
    text = re.sub(
        r"(?i)\b(api[_-]?key|secret|password|passwd|token|authorization)\b(\s*[:=]\s*)(['\"])[^'\"]+\3",
        r"\1\2\3[REDACTED]\3",
        text,
    )
    return text


def _language_for(path: Path) -> str | None:
    name = path.name.lower()
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "Dockerfile"
    if name == "makefile":
        return "Makefile"
    return EXT_LANGUAGE.get(path.suffix.lower())


def _score(rel: str) -> int:
    name = Path(rel).name.lower()
    lowered = rel.lower().replace("\\", "/")
    if name.startswith("readme"):
        return 100
    if name in {"package.json", "pyproject.toml", "requirements.txt", "pipfile", "go.mod", "cargo.toml", "composer.json", "gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml"}:
        return 95
    if name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "vercel.json", "render.yaml", "fly.toml", "procfile", "netlify.toml", "serverless.yml"}:
        return 90
    if name in {"schema.prisma"} or "/.github/workflows/" in f"/{lowered}":
        return 88
    if any(part in lowered for part in ("/routes/", "/route/", "/api/", "/controllers/", "/middleware/", "/models/", "/auth/")):
        return 75
    if name.startswith("test") or name.endswith("_test.py") or ".spec." in name or ".test." in name:
        return 35
    if name in LOCKFILES:
        return 1
    return 45


def _is_sensitive_env(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith(".env") and "example" not in name and "sample" not in name and "template" not in name:
        return True
    return name in {"credentials.json", "secrets.json", "id_rsa", "id_dsa"}


def _walk(root: Path) -> tuple[list[dict], list[dict]]:
    files = []
    skipped = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORE_DIRS and not name.startswith(".git")]
        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                rel = path.relative_to(root).as_posix()
                size = path.stat().st_size
            except OSError as exc:
                skipped.append({"path": str(path), "reason": str(exc)})
                continue
            files.append({"path": rel, "abs": str(path), "size": size, "language": _language_for(path), "score": _score(rel)})
    return files, skipped


def _read_text(path: Path, limit: int = MAX_FILE_BYTES) -> str | None:
    if _is_sensitive_env(path):
        return None
    try:
        raw = path.read_bytes()[:limit]
    except OSError:
        return None
    if b"\0" in raw[:1024]:
        return None
    return raw.decode("utf-8", errors="replace")


def _symbols(rel: str, lines: list[str]) -> list[dict]:
    found = []
    ext = Path(rel).suffix.lower()
    for number, line in enumerate(lines, start=1):
        name = None
        kind = None
        if ext == ".py":
            match = re.match(r"^(?:async\s+def|def)\s+(\w+)\s*\(", line)
            if match:
                name, kind = match.group(1), "function"
            match = re.match(r"^class\s+(\w+)", line)
            if match:
                name, kind = match.group(1), "class"
        elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs"}:
            match = re.match(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", line.strip())
            if match:
                name, kind = match.group(1), "function"
            match = re.match(r"^(?:export\s+)?class\s+(\w+)", line.strip())
            if match:
                name, kind = match.group(1), "class"
        elif ext == ".go":
            match = re.match(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", line.strip())
            if match:
                name, kind = match.group(1), "function"
        elif ext in {".java", ".kt", ".cs"}:
            match = re.search(r"\bclass\s+(\w+)", line)
            if match:
                name, kind = match.group(1), "class"
        if name and name not in {"if", "for", "while", "switch"}:
            found.append({"name": name, "kind": kind, "file": rel, "line": number})
        if len(found) >= 6:
            break
    return found


def _snippet(lines: list[str], line: int) -> str:
    start = max(0, line - 6)
    end = min(len(lines), line + 10)
    body = "\n".join(f"{index + start + 1}: {lines[index]}" for index in range(start, end) if start + index < len(lines))
    # fix indexing: lines[start:end]
    chunk = lines[start:end]
    body = "\n".join(f"{start + offset + 1}: {text}" for offset, text in enumerate(chunk))
    return redact(body)


def _imports_in_line(line: str) -> list[str]:
    found = []
    for match in re.finditer(r"""(?:from\s+([A-Za-z0-9_\.]+)\s+import|^\s*import\s+([A-Za-z0-9_\.]+)|require\(\s*['\"]([^'\"]+)['\"]|import\s+(?:[^'\";]+from\s+)?['\"]([^'\"]+)['\"]|from\s+['\"]([^'\"]+)['\"])""", line):
        value = next((group for group in match.groups() if group), None)
        if value:
            found.append(value)
    return found


def _normalize_import(value: str) -> str:
    value = value.strip()
    if value.startswith("@"):
        parts = value.split("/")
        return "/".join(parts[:2]) if len(parts) > 1 else value
    return value.split("/")[0].split(".")[0]


def _scan_manifests(files: list[dict], root: Path) -> list[dict]:
    by_name = {item["path"]: item for item in files}
    deps = []

    def add(name: str, version: str | None, manifest: str, ecosystem: str) -> None:
        clean = name.strip().strip("\"'")
        if not clean or clean.startswith("#") or clean.startswith("-"):
            return
        deps.append({
            "name": clean,
            "version": version,
            "manifest": manifest,
            "ecosystem": ecosystem,
            "used_in": [],
            "typical_purpose": PURPOSE.get(clean.lower()) or PURPOSE.get(clean.split("/")[-1].lower()),
        })

    package = by_name.get("package.json") or next((item for item in files if item["path"].endswith("/package.json")), None)
    for item in files:
        if Path(item["path"]).name != "package.json":
            continue
        text = _read_text(Path(item["abs"]), 400_000)
        if not text:
            continue
        try:
            import json
            data = json.loads(text)
        except Exception:
            continue
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name, version in (data.get(section) or {}).items():
                add(name, str(version), item["path"], "npm")
        item["package_scripts"] = list((data.get("scripts") or {}).keys())
        item["package_description"] = data.get("description")
        item["package_name"] = data.get("name")

    for item in files:
        name = Path(item["path"]).name.lower()
        if name not in {"requirements.txt", "requirements-dev.txt"} and not name.startswith("requirements"):
            continue
        text = _read_text(Path(item["abs"]), 200_000)
        if not text:
            continue
        for line in text.splitlines():
            body = line.split("#", 1)[0].strip()
            if not body or body.startswith("-"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)", body)
            version = None
            version_match = re.search(r"(?:==|>=|~=|<=)\s*([A-Za-z0-9*_.+-]+)", body)
            if version_match:
                version = version_match.group(1)
            if match:
                add(match.group(1), version, item["path"], "pip")

    for item in files:
        if Path(item["path"]).name != "pyproject.toml":
            continue
        text = _read_text(Path(item["abs"]), 200_000) or ""
        for match in re.finditer(r"(?is)dependencies\s*=\s*\[(.*?)\]", text):
            for dep in re.finditer(r"""['\"]([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?""", match.group(1)):
                add(dep.group(1), None, item["path"], "pip")

    for item in files:
        if Path(item["path"]).name == "go.mod":
            text = _read_text(Path(item["abs"])) or ""
            for match in re.finditer(r"^\s*([A-Za-z0-9_.\-/]+)\s+v[0-9][^\s]*", text, re.M):
                module = match.group(1)
                if module.startswith("module") or module == "go":
                    continue
                add(module, None, item["path"], "go")
        if Path(item["path"]).name == "Cargo.toml":
            text = _read_text(Path(item["abs"])) or ""
            in_deps = False
            for line in text.splitlines():
                if line.strip().startswith("["):
                    in_deps = "dependencies" in line.lower()
                elif in_deps:
                    match = re.match(r"""\s*([A-Za-z0-9_-]+)\s*=""", line)
                    if match:
                        add(match.group(1), None, item["path"], "cargo")
        if Path(item["path"]).name == "composer.json":
            text = _read_text(Path(item["abs"])) or ""
            try:
                import json
                data = json.loads(text)
            except Exception:
                data = {}
            for section in ("require", "require-dev"):
                for dep_name, version in (data.get(section) or {}).items():
                    if dep_name != "php":
                        add(dep_name, str(version), item["path"], "composer")
        if Path(item["path"]).name == "Gemfile":
            text = _read_text(Path(item["abs"])) or ""
            for match in re.finditer(r"""gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?""", text):
                add(match.group(1), match.group(2), item["path"], "ruby")
        if Path(item["path"]).name == "pom.xml":
            text = _read_text(Path(item["abs"])) or ""
            for block in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
                artifact = re.search(r"<artifactId>([^<]+)</artifactId>", block)
                version = re.search(r"<version>([^<]+)</version>", block)
                if artifact:
                    add(artifact.group(1), version.group(1) if version else None, item["path"], "maven")
        if "build.gradle" in Path(item["path"]).name:
            text = _read_text(Path(item["abs"])) or ""
            for match in re.finditer(r"""(?:implementation|api|compile)\s*\(?['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]""", text):
                add(match.group(2), match.group(3), item["path"], "gradle")

    # Deduplicate by name + manifest
    unique = []
    seen = set()
    for dep in deps:
        key = (dep["name"].lower(), dep["manifest"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(dep)
    return unique, package


def _mark_used(deps: list[dict], import_hits: dict[str, set[str]]) -> None:
    for dep in deps:
        keys = {dep["name"].lower(), dep["name"].split("/")[-1].lower(), dep["name"].replace("-", "_").lower()}
        for imported, files in import_hits.items():
            if imported.lower() in keys or imported.lower().replace("-", "_") in keys:
                for file in sorted(files):
                    if file not in dep["used_in"]:
                        dep["used_in"].append(file)


def _tree(root: Path, limit: int = 160) -> str:
    lines = [root.name + "/"]
    count = 0

    def walk(directory: Path, prefix: str) -> None:
        nonlocal count
        if count >= limit:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except OSError:
            return
        children = [child for child in children if child.name not in IGNORE_DIRS and child.name != ".git"]
        for index, child in enumerate(children):
            if count >= limit:
                lines.append(prefix + "... truncated")
                return
            last = index == len(children) - 1
            joint = "└── " if last else "├── "
            lines.append(prefix + joint + child.name + ("/" if child.is_dir() else ""))
            count += 1
            if child.is_dir() and prefix.count("│") + prefix.count(" ") < 8:
                walk(child, prefix + ("    " if last else "│   "))

    walk(root, "")
    if count >= limit:
        lines.append("... tree truncated")
    return "\n".join(lines)


def _readme(files: list[dict]) -> dict:
    candidates = [item for item in files if Path(item["path"]).name.lower().startswith("readme")]
    candidates.sort(key=lambda item: (item["path"].count("/"), -item["score"]))
    if not candidates:
        return {"path": None, "text": "", "headings": [], "summary": None}
    item = candidates[0]
    text = _read_text(Path(item["abs"]), 80_000) or ""
    text = redact(text)
    headings = re.findall(r"(?m)^#{1,3}\s+(.+)$", text)
    summary = None
    for paragraph in re.split(r"\n\s*\n", text):
        clean = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", paragraph)
        clean = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", clean)
        clean = re.sub(r"[#>*_`]", "", clean).strip()
        if len(clean) >= 40 and not clean.lower().startswith("license"):
            summary = clean[:500]
            break
    return {"path": item["path"], "text": text[:8000], "headings": headings[:30], "summary": summary}


def _git_history(root: Path, owner: str) -> dict:
    if not (root / ".git").exists():
        return {"available": False, "reason": "This folder has no .git directory, so commit history was not available."}
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "log", "--date=short", "--pretty=format:@@@%H|%an|%ae|%ad|%s", "--numstat"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": f"git log failed ({exc})."}
    if completed.returncode != 0:
        return {"available": False, "reason": (completed.stderr or "git log failed.").strip()}

    authors = defaultdict(lambda: {"commits": 0, "added": 0, "deleted": 0, "email": "", "samples": []})
    current = None
    for line in completed.stdout.splitlines():
        if line.startswith("@@@"):
            parts = line[3:].split("|", 4)
            if len(parts) < 5:
                current = None
                continue
            _commit, name, email, date, subject = parts
            current = (name, email, date, subject)
            slot = authors[name]
            slot["commits"] += 1
            slot["email"] = email
            if len(slot["samples"]) < 3:
                slot["samples"].append({"date": date, "subject": subject[:160]})
            continue
        if not current or "\t" not in line:
            continue
        added, deleted, _path = (line.split("\t", 2) + ["", "", ""])[:3]
        slot = authors[current[0]]
        if added.isdigit():
            slot["added"] += int(added)
        if deleted.isdigit():
            slot["deleted"] += int(deleted)

    rows = []
    owner_commits = 0
    total_commits = 0
    for name, slot in authors.items():
        email = slot["email"]
        match = _author_matches(name, email, owner)
        total_commits += slot["commits"]
        if match:
            owner_commits += slot["commits"]
        rows.append({
            "name": name,
            "email": email,
            "commits": slot["commits"],
            "added": slot["added"],
            "deleted": slot["deleted"],
            "matches_owner_hint": match,
            "samples": slot["samples"],
        })
    rows.sort(key=lambda item: (-item["commits"], item["name"].lower()))
    return {
        "available": True,
        "authors": rows[:12],
        "author_count": len(authors),
        "total_commits": total_commits,
        "owner_hint_commits": owner_commits,
        "reason": None,
    }


def _author_matches(name: str, email: str, owner: str) -> bool:
    if not owner:
        return False
    owner_l = owner.lower()
    email_l = (email or "").lower()
    local = email_l.split("@", 1)[0]
    if owner_l == local or local.endswith("+" + owner_l) or local.endswith(owner_l):
        if email_l.endswith("@users.noreply.github.com") or owner_l == local:
            return True
    compact = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return compact == owner_l


def _boilerplate(files: list[dict], root: Path) -> list[dict]:
    found = []
    for item in files:
        name = Path(item["path"]).name.lower()
        reason = None
        if name in LOCKFILES:
            reason = "Lockfile generated by a package manager."
        elif name.endswith(".min.js") or name.endswith(".map"):
            reason = "Minified or generated bundle."
        else:
            text = _read_text(Path(item["abs"]), 4000) or ""
            head = "\n".join(text.splitlines()[:12]).lower()
            if any(marker in head for marker in ("generated by", "auto-generated", "autogenerated", "do not edit", "@generated")):
                reason = "File header says it was generated."
        if reason and len(found) < 40:
            found.append({"path": item["path"], "reason": reason})
    return found


def analyze_tree(root: Path, meta: dict, github: dict | None, api_error: str | None, clone_note: str) -> dict:
    files, skipped = _walk(root)
    dependencies, _package_item = _scan_manifests(files, root)
    readme = _readme(files)

    ranked = sorted(
        [item for item in files if Path(item["path"]).name.lower() not in LOCKFILES],
        key=lambda item: (-item["score"], -item["size"]),
    )
    deep = ranked[:MAX_DEEP_FILES]
    not_scanned = max(0, len(ranked) - len(deep))

    import_hits: dict[str, set[str]] = defaultdict(set)
    routes = []
    urls = []
    symbols = []
    security = []
    db_notes = []
    ml_notes = []
    protocol_notes = []
    quality_try = 0
    quality_calls = 0
    todo_count = 0
    large_files = []
    excerpts = []
    line_counts = defaultdict(int)
    byte_counts = defaultdict(int)
    file_counts = defaultdict(int)
    sample_files = defaultdict(list)
    roles = defaultdict(set)
    scanned_content_files = 0
    committed_env = []
    submodules = []

    for item in files:
        language = item["language"]
        if language:
            byte_counts[language] += item["size"]
            file_counts[language] += 1
            if len(sample_files[language]) < 8:
                sample_files[language].append(item["path"])
            lowered = item["path"].lower()
            if "/test" in lowered or lowered.startswith("test") or ".spec." in lowered or ".test." in lowered:
                roles[language].add("tests")
            elif ".github/workflows" in lowered:
                roles[language].add("CI configuration")
            elif "dockerfile" in lowered or language == "Dockerfile":
                roles[language].add("container build")
            elif "/migrations/" in lowered or "schema.prisma" in lowered:
                roles[language].add("database schema")
            else:
                roles[language].add("repository source or configuration")
        if _is_sensitive_env(Path(item["abs"])):
            committed_env.append(item["path"])

    gitmodules = root / ".gitmodules"
    if gitmodules.exists():
        text = _read_text(gitmodules) or ""
        submodules = re.findall(r"(?m)^url\s*=\s*(\S+)", text)

    excerpt_budget = 8
    for item in deep:
        text = _read_text(Path(item["abs"]))
        if text is None:
            continue
        scanned_content_files += 1
        lines = text.splitlines()
        language = item["language"]
        if language and item["size"] <= MAX_FILE_BYTES:
            line_counts[language] += len(lines)
        if len(lines) > 400 and language and language not in NON_PRIMARY:
            large_files.append({"path": item["path"], "lines": len(lines)})
        todo_count += len(re.findall(r"(?i)\b(TODO|FIXME)\b", text))
        if re.search(r"\b(try\s*[:{]|catch\s*\()", text):
            quality_try += 1
        if re.search(r"\b(fetch|axios|requests\.(get|post|put|patch|delete)|http\.(get|post))\b", text):
            quality_calls += 1

        for line_number, line in enumerate(lines, start=1):
            for imported in _imports_in_line(line):
                import_hits[_normalize_import(imported)].add(item["path"])
            for pattern in ROUTE_PATTERNS:
                for match in pattern.finditer(line):
                    if len(routes) < 80:
                        method = "SEE FILE"
                        method_match = re.search(r"\b(get|post|put|patch|delete|route|path|Get|Post|Put|Patch|Delete)\b", line)
                        if method_match:
                            method = method_match.group(1).upper()
                            if method == "ROUTE":
                                method = "ANY"
                            if method == "PATH":
                                method = "ANY"
                        routes.append({"method": method, "path": match.group(1), "file": item["path"], "line": line_number})
            if "http://" in line or "https://" in line:
                for match in URL_PATTERN.finditer(line):
                    url = match.group(0).rstrip(".,);")
                    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
                    if any(host.endswith(skipped) for skipped in SKIP_HOSTS):
                        continue
                    if len(urls) < 50 and not any(existing["url"] == url for existing in urls):
                        urls.append({"url": url, "file": item["path"], "line": line_number})
            if re.search(r"(?i)\b(mongoose|prisma|sequelize|typeorm|sqlalchemy|pymongo|psycopg|mongodb|firebase|create table|@relation|foreignkey)\b", line):
                if len(db_notes) < 40:
                    db_notes.append({"file": item["path"], "line": line_number, "text": redact(line.strip())[:180]})
            if re.search(r"(?i)\b(tensorflow|torch|sklearn|transformers|from_pretrained|\.fit\(|keras|cv2|mediapipe)\b", line):
                if len(ml_notes) < 40:
                    ml_notes.append({"file": item["path"], "line": line_number, "text": redact(line.strip())[:180]})
            if re.search(r"(?i)\b(graphql|socket\.io|websocket|ws://|wss://)\b", line):
                if len(protocol_notes) < 20:
                    protocol_notes.append({"file": item["path"], "line": line_number, "text": redact(line.strip())[:180]})
            for kind, pattern in SECRET_PATTERNS:
                if pattern.search(line) and not PLACEHOLDER.search(line):
                    security.append({"kind": kind, "file": item["path"], "line": line_number})
                    break
        symbols.extend(_symbols(item["path"], lines))
        if excerpt_budget and item["score"] >= 45 and language and language not in {"JSON", "YAML", "TOML", "XML", "Markdown"}:
            excerpts.append({"file": item["path"], "text": redact("\n".join(f"{n}: {line}" for n, line in enumerate(lines[:EXCERPT_LINES], start=1)))})
            excerpt_budget -= 1

    _mark_used(dependencies, import_hits)
    symbols = symbols[:250]
    for symbol in symbols:
        # snippets filled lazily from already scanned files is expensive; attach later only for selected
        pass

    languages = []
    for name in byte_counts:
        languages.append({
            "name": name,
            "files": file_counts[name],
            "bytes": byte_counts[name],
            "lines_scanned": line_counts.get(name, 0),
            "sample_files": sample_files[name],
            "roles": sorted(roles[name]),
        })
    languages.sort(key=lambda item: (-item["bytes"], item["name"]))
    primary = next((item["name"] for item in languages if item["name"] not in NON_PRIMARY), None)

    def used_named(names: set[str]) -> list[dict]:
        rows = []
        for dep in dependencies:
            if dep["name"].lower() in names or dep["name"].split("/")[-1].lower() in names:
                rows.append(dep)
        return rows

    package_meta = {}
    for item in files:
        if Path(item["path"]).name == "package.json" and item["path"].count("/") == 0:
            package_meta = {
                "name": item.get("package_name"),
                "description": item.get("package_description"),
                "scripts": item.get("package_scripts") or [],
                "path": item["path"],
            }
            break

    tool_files = []
    tool_names = (
        "dockerfile", "docker-compose.yml", "docker-compose.yaml", "vercel.json",
        "render.yaml", "fly.toml", "procfile", "netlify.toml", "serverless.yml",
        "app.yaml", "cloudbuild.yaml",
    )
    for item in files:
        lowered = item["path"].lower()
        base = Path(item["path"]).name.lower()
        if base in tool_names or base.startswith("dockerfile") or "/.github/workflows/" in f"/{lowered}" or lowered.startswith(".github/workflows/"):
            tool_files.append(item["path"])
        elif base in {".gitignore"} or lowered.startswith(".vscode/") or lowered.startswith(".idea/"):
            tool_files.append(item["path"])

    test_files = [
        item["path"] for item in files
        if re.search(r"(?i)(^|/)(tests?|spec)/|test_.*\.py$|_test\.(py|go)$|\.(spec|test)\.[jt]sx?$", item["path"])
    ]

    history = _git_history(root, meta.get("owner") or "")
    generated = _boilerplate(files, root)

    # Attach snippets for the first few non-test symbols by re-reading those files.
    attached = 0
    for symbol in symbols:
        if "/test" in symbol["file"].lower() or symbol["file"].lower().startswith("test"):
            continue
        path = root / symbol["file"]
        text = _read_text(path)
        if not text:
            continue
        symbol["snippet"] = _snippet(text.splitlines(), symbol["line"])
        attached += 1
        if attached >= 8:
            break

    return {
        "source": {
            "owner": meta.get("owner"),
            "repo": meta.get("repo"),
            "url": meta.get("url"),
            "branch": meta.get("branch"),
            "clone_note": clone_note,
        },
        "github": github,
        "github_api_error": api_error,
        "readme": readme,
        "package": package_meta,
        "tree": _tree(root),
        "file_count": len(files),
        "deep_scanned_files": scanned_content_files,
        "unscanned_text_files": not_scanned,
        "skipped": skipped[:20],
        "languages": languages,
        "primary_language": primary,
        "dependencies": dependencies,
        "frontend_dependencies": used_named(FRONTEND_NAMES),
        "backend_dependencies": used_named(BACKEND_NAMES),
        "database_dependencies": used_named(DB_NAMES),
        "ml_dependencies": used_named(ML_NAMES),
        "routes": routes,
        "external_urls": urls,
        "protocols": protocol_notes,
        "db_notes": db_notes,
        "ml_notes": ml_notes,
        "security_findings": security[:30],
        "committed_env_files": committed_env,
        "symbols": [{key: value for key, value in symbol.items() if key != "snippet" or value} for symbol in symbols],
        "excerpts": excerpts,
        "tool_files": tool_files,
        "test_files": test_files[:40],
        "test_file_count": len(test_files),
        "todo_count": todo_count,
        "large_files": sorted(large_files, key=lambda item: -item["lines"])[:15],
        "files_with_error_handling": quality_try,
        "files_with_http_calls": quality_calls,
        "submodules": submodules,
        "history": history,
        "generated_files": generated,
        "interface_files": [
            item["path"] for item in files
            if item.get("language") in {"JavaScript", "TypeScript", "Vue", "Svelte", "CSS", "SCSS", "Sass", "HTML"}
        ][:40],
        "schema_files": [
            item["path"] for item in files
            if item["path"].endswith(".prisma") or item["path"].endswith(".sql") or "/models/" in item["path"].lower() or "schema" in Path(item["path"]).name.lower()
        ][:30],
        "limitations": [
            f"Deep content scan read {scanned_content_files} files. {not_scanned} other non-lock files were counted by size and extension only."
            if not_scanned else
            f"Deep content scan read {scanned_content_files} text files.",
            "Ignored directories include dependencies, build output, and virtual environments.",
            "Secret-like values are never copied into this report.",
            clone_note,
        ],
    }
