"""Render an evidence-based repository analysis report."""

from __future__ import annotations

CATEGORY_RULES = [
    ("AI/ML", {"tensorflow", "torch", "pytorch", "scikit-learn", "sklearn", "keras", "transformers", "opencv-python", "cv2", "mediapipe"}),
    ("Web development", {"react", "vue", "angular", "@angular/core", "next", "express", "django", "flask", "fastapi", "spring-boot", "nestjs"}),
    ("Blockchain", {"web3", "ethers", "hardhat", "solidity"}),
    ("IoT", {"mqtt", "paho-mqtt"}),
    ("Cybersecurity", {"cryptography", "pycryptodome", "bandit"}),
]


def _used(deps: list[dict]) -> list[dict]:
    return [dep for dep in deps if dep.get("used_in")]


def _declared_only(deps: list[dict]) -> list[dict]:
    return [dep for dep in deps if not dep.get("used_in")]


def _bullet(items: list[str]) -> str:
    if not items:
        return "- None found in the scanned files.\n"
    return "".join(f"- {item}\n" for item in items)


def _dep_line(dep: dict) -> str:
    version = dep.get("version") or "version not pinned in the manifest entry that was read"
    purpose = dep.get("typical_purpose") or "No standard purpose was inferred for this name."
    used = ", ".join(dep.get("used_in") or []) or "no import of this name was found in scanned source"
    return f"{dep['name']} ({version}) in `{dep['manifest']}` — {purpose} Used in: {used}."


def _categories(analysis: dict) -> list[str]:
    names = {dep["name"].lower() for dep in analysis["dependencies"] if dep.get("used_in")}
    names.update(note["text"].lower() for note in analysis.get("ml_notes") or [])
    found = []
    for label, keys in CATEGORY_RULES:
        if any(any(key in blob for key in keys) for blob in names):
            found.append(label)
    return found


def _complexity(analysis: dict) -> tuple[str, list[str]]:
    reasons = []
    points = 0
    used = _used(analysis["dependencies"])
    if len(used) >= 8:
        points += 3
        reasons.append(f"{len(used)} dependencies are imported in source.")
    elif used:
        points += 1
        reasons.append(f"{len(used)} dependencies are imported in source.")
    if analysis["routes"]:
        points += 2
        reasons.append(f"{len(analysis['routes'])} route-like declarations were found.")
    if analysis["database_dependencies"] or analysis["db_notes"]:
        points += 2
        reasons.append("Database access code or a database library was found.")
    if analysis["external_urls"]:
        points += 1
        reasons.append("External URL literals were found.")
    if analysis["ml_notes"] or _used(analysis["ml_dependencies"]):
        points += 3
        reasons.append("Machine learning library usage was found.")
    if analysis["test_file_count"]:
        points += 1
        reasons.append("Test files are present.")
    if any("workflows" in path or "Dockerfile" in path or path.lower().endswith("dockerfile") for path in analysis["tool_files"]):
        points += 1
        reasons.append("CI or container configuration is present.")
    if points >= 9:
        label = "High"
    elif points >= 4:
        label = "Moderate"
    else:
        label = "Low"
    reasons.append(f"Heuristic score: {points}. This is not a measure of the candidate's skill.")
    return label, reasons


def _mermaid(analysis: dict) -> str:
    nodes = []
    edges = []
    if analysis["interface_files"] and analysis["frontend_dependencies"]:
        nodes.append("ui[Frontend files]")
    if analysis["routes"] or _used(analysis["backend_dependencies"]):
        nodes.append("api[Backend or route handlers]")
    if analysis["db_notes"] or _used(analysis["database_dependencies"]):
        nodes.append("db[(Database code)]")
    if analysis["external_urls"]:
        nodes.append("ext[External URL literals]")
    if analysis["ml_notes"] or _used(analysis["ml_dependencies"]):
        nodes.append("ml[ML library usage]")
    if not nodes:
        nodes.append("repo[Repository source]")
    route_files = {route["file"] for route in analysis["routes"]}
    db_files = {note["file"] for note in analysis["db_notes"]}
    url_files = {item["file"] for item in analysis["external_urls"]}
    if "ui[Frontend files]" in nodes and "api[Backend or route handlers]" in nodes:
        if route_files & set(analysis["interface_files"]):
            edges.append("ui --> api")
    if "api[Backend or route handlers]" in nodes and "db[(Database code)]" in nodes and (route_files & db_files):
        edges.append("api --> db")
    if "api[Backend or route handlers]" in nodes and "ext[External URL literals]" in nodes and (route_files & url_files):
        edges.append("api --> ext")
    if "ml[ML library usage]" in nodes and "api[Backend or route handlers]" in nodes:
        ml_files = {note["file"] for note in analysis["ml_notes"]}
        if ml_files & route_files:
            edges.append("api --> ml")
    lines = ["```mermaid", "flowchart LR"]
    lines.extend(f"  {node}" for node in nodes)
    lines.extend(f"  {edge}" for edge in edges)
    lines.append("```")
    if not edges and len(nodes) > 1:
        lines.append("")
        lines.append("No scanned file both declares a route and contains the database or external URL evidence, so the diagram does not invent a connection.")
    return "\n".join(lines)


def _questions(analysis: dict) -> list[dict]:
    primary = analysis.get("primary_language") or "the main language"
    symbols = [symbol for symbol in analysis["symbols"] if symbol.get("snippet")]
    symbol = symbols[0] if symbols else None
    second = symbols[1] if len(symbols) > 1 else symbol
    route = analysis["routes"][0] if analysis["routes"] else None
    used = _used(analysis["dependencies"])
    library = used[0] if used else None
    http_file = analysis["external_urls"][0] if analysis["external_urls"] else None
    questions = []

    questions.append({
        "level": "Level 1 – Fundamentals",
        "difficulty": "Fundamentals",
        "technology": primary,
        "location": (analysis["languages"][0]["sample_files"][0] if analysis["languages"] else "repository root"),
        "question": f"Why is {primary} used in this repository, and which part of the project depends on it?",
        "expected": "The candidate should point at the files that are actually written in that language and give a reason tied to the problem, the ecosystem, or a constraint. The repository does not record the reason for the choice.",
        "concepts": [primary, "where that language appears in this repo"],
        "follow_ups": [f"Which files would break first if {primary} were replaced?"],
        "evaluation": "Credit file-level knowledge. Do not require a reason that is not written in the repo.",
    })
    if library:
        questions.append({
            "level": "Level 1 – Fundamentals",
            "difficulty": "Fundamentals",
            "technology": library["name"],
            "location": library["used_in"][0],
            "question": f"Why was {library['name']} imported in `{library['used_in'][0]}` instead of doing that work without the library?",
            "expected": f"They should explain the job {library['name']} is doing in that file. A typical role of this package is: {library.get('typical_purpose') or 'not inferred'}.",
            "concepts": [library["name"], "dependency versus handwritten code"],
            "follow_ups": ["What would you have to reimplement if this import were removed?"],
            "evaluation": "A strong answer names the calls in that file. Repeating the package slogan without the file is weak.",
        })
    if route:
        questions.append({
            "level": "Level 2 – Implementation",
            "difficulty": "Implementation",
            "technology": "HTTP routing",
            "location": f"{route['file']}:{route['line']}",
            "question": f"Walk through the `{route['method']} {route['path']}` handler in `{route['file']}` from the incoming request to the response.",
            "expected": "They should describe the handler that exists at that line, including validation, storage, and the response it builds. Do not accept a generic framework tutorial that never mentions this route.",
            "concepts": ["route", "request", "response", "status handling"],
            "follow_ups": ["What happens if a required field is missing?"],
            "evaluation": "The answer should match the handler body, not a remembered boilerplate example.",
        })
    elif symbol:
        questions.append({
            "level": "Level 2 – Implementation",
            "difficulty": "Implementation",
            "technology": primary,
            "location": f"{symbol['file']}:{symbol['line']}",
            "question": f"How does `{symbol['name']}` in `{symbol['file']}` work, from its inputs to its result?",
            "expected": "They should trace the function using the code below. The report has not executed it.",
            "concepts": [symbol["name"], "control flow"],
            "follow_ups": ["What input would make this fail?"],
            "evaluation": "Look for a line-by-line explanation of this function, not a description of the whole project.",
        })
    if symbol:
        questions.append({
            "level": "Level 3 – Code-Level Understanding",
            "difficulty": "Code-level",
            "technology": primary,
            "location": f"{symbol['file']}:{symbol['line']}",
            "question": f"Explain `{symbol['name']}` at `{symbol['file']}:{symbol['line']}`. What does each branch or call in this excerpt do?\n\n```\n{symbol['snippet']}\n```",
            "expected": "They should explain the visible calls and branches. If a line is a library call, they should say what is passed in and what is done with the result.",
            "concepts": [symbol["name"], "reading the excerpt rather than recalling a template"],
            "follow_ups": ["What would you rename or split here, and why?"],
            "evaluation": "Correct reading of this excerpt is required. Invented helpers that are not in the excerpt do not count.",
        })
    if second and second is not symbol:
        questions.append({
            "level": "Level 3 – Code-Level Understanding",
            "difficulty": "Code-level",
            "technology": primary,
            "location": f"{second['file']}:{second['line']}",
            "question": f"Trace `{second['name']}` in `{second['file']}` and name the other project functions it depends on.\n\n```\n{second['snippet']}\n```",
            "expected": "They should identify calls that appear in the excerpt and say which of those are local to the repository.",
            "concepts": ["call graph", second["name"]],
            "follow_ups": ["Which of those calls talk to a database or the network?"],
            "evaluation": "The trace has to stay inside the shown code and files they can open.",
        })
    smell_file = None
    if analysis["files_with_http_calls"] and symbol:
        smell_file = symbol["file"]
        has_handler = "try" in (symbol.get("snippet") or "").lower() or "catch" in (symbol.get("snippet") or "").lower()
        questions.append({
            "level": "Level 4 – Debugging and Problem Solving",
            "difficulty": "Debugging",
            "technology": "Error handling",
            "location": f"{symbol['file']}:{symbol['line']}",
            "question": (
                f"The HTTP or client call around `{symbol['name']}` fails with a timeout. "
                + ("The excerpt already has a try or catch. What does that path actually return to the caller?"
                   if has_handler else
                   "The excerpt does not show a try/except or .catch. What does the caller see today, and where would you handle the timeout?")
            ),
            "expected": "They should say what the current code does on failure, based on the excerpt, and then where a timeout should be handled without hiding the error.",
            "concepts": ["timeouts", "error propagation", "what the caller observes"],
            "follow_ups": ["How would you log this without writing secrets to the log?"],
            "evaluation": "The diagnosis must match the excerpt. A generic 'add try/catch' with no mention of the caller is incomplete.",
        })
    if route:
        questions.append({
            "level": "Level 4 – Debugging and Problem Solving",
            "difficulty": "Debugging",
            "technology": "HTTP routing",
            "location": f"{route['file']}:{route['line']}",
            "question": f"Clients report that `{route['method']} {route['path']}` sometimes returns a success status when the work did not finish. How would you confirm that in `{route['file']}`?",
            "expected": "They should point at the status this handler sends and the condition that chooses it. If the file has no test, they should say how they would reproduce it.",
            "concepts": ["status codes", "reproduction", "reading the handler"],
            "follow_ups": ["Which test file, if any, already covers this route?"],
            "evaluation": "Credit a concrete check in this file. Do not require a test that is not in the repository.",
        })
    questions.append({
        "level": "Level 5 – Architecture and System Design",
        "difficulty": "Architecture",
        "technology": "System design",
        "location": analysis["readme"]["path"] or "repository layout",
        "question": "The repository does not document a production load. If this project had to serve more concurrent users, which current module would you change first, and what evidence in the repo makes that the bottleneck?",
        "expected": "They should name a real file or integration from this repository, such as a route handler, a database call, or an external URL, and say what they would measure. They should not invent infrastructure that is not configured here.",
        "concepts": ["bottleneck", "statelessness", "what this repo actually deploys"],
        "follow_ups": ["Which deployment file, if any, would have to change?"],
        "evaluation": "A good answer stays inside the detected stack. Extra cloud services need to be labeled as a proposal, not as the current design.",
    })
    if analysis["database_dependencies"] or analysis["db_notes"]:
        db_file = (analysis["db_notes"][0]["file"] if analysis["db_notes"] else analysis["database_dependencies"][0]["used_in"][0] if _used(analysis["database_dependencies"]) else analysis["database_dependencies"][0]["manifest"])
        questions.append({
            "level": "Level 5 – Architecture and System Design",
            "difficulty": "Architecture",
            "technology": "Database",
            "location": db_file,
            "question": f"Looking at `{db_file}`, how would you add an index or cache only if the access pattern in this code needs it?",
            "expected": "They should point at the query or model field that is filtered or joined. If no query is visible, they should say the access pattern is not shown and they would not add an index blindly.",
            "concepts": ["queries", "indexes", "not optimizing code they have not read"],
            "follow_ups": ["What would you measure before adding a cache?"],
            "evaluation": "Credit refusal to invent an index when the query is not in the file.",
        })
    if library:
        questions.append({
            "level": "Level 6 – Ownership Verification",
            "difficulty": "Ownership",
            "technology": library["name"],
            "location": library["used_in"][0],
            "question": f"In `{library['used_in'][0]}`, remove {library['name']} and replace that call with a short version you write here. What behavior would change?",
            "expected": "Someone who wrote or understands the integration can say which arguments are passed and which edge cases the library was covering. A candidate who only installed the package will describe the README, not this call site.",
            "concepts": [library["name"], "call-site ownership"],
            "follow_ups": ["Which test would fail after that change?"],
            "evaluation": "Match the answer to the call site. Vague familiarity with the library name is not ownership of this code.",
        })
    history = analysis["history"]
    questions.append({
        "level": "Level 6 – Ownership Verification",
        "difficulty": "Ownership",
        "technology": "Git history",
        "location": "git log",
        "question": "Which parts of this repository did you write yourself, which were generated, and which came from a dependency or a fork?",
        "expected": (
            "Compare the answer with the commit authors and generated-file list in this report. "
            + (f"The fetched history has {history['total_commits']} commits from {history['author_count']} "
               f"{'author' if history['author_count'] == 1 else 'authors'}."
               if history.get("available") else "Commit history was not available, so authorship cannot be checked from git.")
        ),
        "concepts": ["authorship", "generated code", "dependencies"],
        "follow_ups": ["Open a file you claim you wrote and explain one decision that is not required by the framework."],
        "evaluation": "Do not treat repository ownership as proof they wrote every file. Agreement with the commit record and with generated-file headers is the signal.",
    })
    if http_file and smell_file is None:
        questions.append({
            "level": "Level 4 – Debugging and Problem Solving",
            "difficulty": "Debugging",
            "technology": "HTTP client",
            "location": f"{http_file['file']}:{http_file['line']}",
            "question": f"The request to `{http_file['url']}` in `{http_file['file']}` starts returning an unexpected body. How would you isolate whether the bug is the URL, the headers, or the parsing in that file?",
            "expected": "They should separate building the request, sending it, and reading the response, using this call site.",
            "concepts": ["HTTP", "parsing", "isolation"],
            "follow_ups": ["What would you avoid logging?"],
            "evaluation": "The steps should reference this file. Do not accept a packet-capture tutorial as a substitute.",
        })
    return questions


def _question_markdown(question: dict) -> str:
    follow = "\n".join(f"  - {item}" for item in question["follow_ups"])
    concepts = ", ".join(question["concepts"])
    return (
        f"#### {question['level']}\n\n"
        f"**Question.** {question['question']}\n\n"
        f"- Difficulty: {question['difficulty']}\n"
        f"- Technology: {question['technology']}\n"
        f"- Location: `{question['location']}`\n"
        f"- Expected from the candidate: {question['expected']}\n"
        f"- Key concepts: {concepts}\n"
        f"- Follow-ups:\n{follow}\n"
        f"- Evaluation: {question['evaluation']}\n"
    )


def render_markdown(analysis: dict) -> str:
    source = analysis["source"]
    github = analysis.get("github") or {}
    readme = analysis["readme"]
    used = _used(analysis["dependencies"])
    unused = _declared_only(analysis["dependencies"])
    categories = _categories(analysis)
    complexity, complexity_reasons = _complexity(analysis)
    history = analysis["history"]
    primary = analysis.get("primary_language")
    title = analysis.get("package", {}).get("name") or source["repo"]
    description = (analysis.get("package") or {}).get("description") or github.get("description") or readme.get("summary")

    parts = []
    parts.append(f"# Repository analysis: {source['owner']}/{source['repo']}\n")
    parts.append(f"Source: {source['url']}\n")
    parts.append("Confirmed statements name a file or a command output. Sentences marked as inference are not written in the repository.\n")
    parts.append("## Limitations\n")
    parts.append(_bullet(analysis["limitations"] + ([analysis["github_api_error"]] if analysis.get("github_api_error") else [])))

    parts.append("## 1. Project overview\n")
    parts.append(f"- Project name: {title}\n")
    parts.append(f"- Description: {description or 'No description was found in the GitHub API, package manifest, or README opening.'}\n")
    if github:
        parts.append(f"- GitHub topics: {', '.join(github.get('topics') or []) or 'none'}\n")
        parts.append(f"- License reported by the GitHub API: {github.get('license') or 'not reported'}\n")
        parts.append(f"- Fork: {'yes, parent ' + github['parent'] if github.get('fork') and github.get('parent') else 'yes' if github.get('fork') else 'no'}\n")
    parts.append(f"- Problem statement: {readme['summary'] or 'The README does not contain a usable opening description.'}\n")
    if readme["headings"]:
        parts.append("- README sections (these are claims in the document, not verified features):\n")
        parts.append("".join(f"  - {heading}\n" for heading in readme["headings"][:20]))
    else:
        parts.append("- README sections: none found.\n")
    parts.append("- Real-world use cases: only those implied by the description above. None were extracted as a separate, explicit list.\n")
    if categories:
        parts.append(f"- Category (inference from libraries that are imported or from ML-related lines): {', '.join(categories)}.\n")
    else:
        parts.append("- Category: not assigned. No category keyword was confirmed in imported libraries.\n")
    parts.append("- Working mechanism: see section 11. This overview does not add behavior that section cannot support.\n")
    if readme["path"]:
        parts.append(f"- README path: `{readme['path']}`\n")

    parts.append("\n## 2. Programming languages\n")
    if not analysis["languages"]:
        parts.append("No recognized source languages were found.\n")
    for language in analysis["languages"]:
        samples = ", ".join(f"`{path}`" for path in language["sample_files"])
        parts.append(
            f"- **{language['name']}** — {language['files']} files, about {language['bytes']:,} bytes, "
            f"{language['lines_scanned']:,} lines in files that were read. "
            f"Role from paths: {', '.join(language['roles']) or 'unspecified'}. "
            f"Examples: {samples}.\n"
        )
    parts.append(f"\nPrimary programming language by file bytes, excluding Markdown, JSON, YAML, TOML, and XML: **{primary or 'not identified'}**.\n")
    if github.get("primary_language") and github.get("primary_language") != primary:
        parts.append(f"GitHub Linguist reports `{github['primary_language']}`. The byte count above can disagree with Linguist.\n")

    parts.append("\n## 3. Frameworks and libraries\n")
    parts.append("Imported dependencies are treated as used. Manifest entries with no matching import in the scanned source are listed separately and are not claimed as implementation.\n\n")
    parts.append("### Used in scanned source\n")
    parts.append(_bullet([_dep_line(dep) for dep in used]) if used else "- No imported dependency matched a parsed manifest.\n")
    parts.append("\n### Declared but not seen in an import\n")
    shown_unused = unused[:40]
    parts.append(_bullet([_dep_line(dep) for dep in shown_unused]) if shown_unused else "- None.\n")
    if len(unused) > len(shown_unused):
        parts.append(f"\n{len(unused) - len(shown_unused)} more declared dependencies were omitted from this list.\n")

    parts.append("\n## 4. Frontend analysis\n")
    front_used = _used(analysis["frontend_dependencies"])
    front_unused = _declared_only(analysis["frontend_dependencies"])
    if not front_used and not analysis["interface_files"]:
        parts.append("No frontend framework import or interface file type (JS, TS, Vue, Svelte, CSS, HTML) was found.\n")
    else:
        parts.append("### Libraries imported\n")
        parts.append(_bullet([_dep_line(dep) for dep in front_used]) if front_used else "- No frontend library import was matched.\n")
        if front_unused:
            parts.append("\n### Declared frontend libraries with no matching import\n")
            parts.append(_bullet([f"{dep['name']} in `{dep['manifest']}`" for dep in front_unused]))
        parts.append("\n### Interface files\n")
        parts.append(_bullet([f"`{path}`" for path in analysis["interface_files"][:25]]) if analysis["interface_files"] else "- None.\n")
        parts.append("\nAuthentication, routing, and form handling are reported only when a matching library was imported. See those library rows above.\n")

    parts.append("\n## 5. Backend analysis\n")
    back_used = _used(analysis["backend_dependencies"])
    if not back_used and not analysis["routes"]:
        parts.append("No backend framework import and no route-like declaration were found in the scanned files.\n")
    else:
        parts.append(_bullet([_dep_line(dep) for dep in back_used]) if back_used else "- No backend framework import was matched.\n")
        parts.append("\n### Route-like declarations\n")
        if analysis["routes"]:
            parts.append(_bullet([
                f"`{route['method']} {route['path']}` in `{route['file']}:{route['line']}`"
                for route in analysis["routes"][:40]
            ]))
        else:
            parts.append("- No route decorator or `method('/path')` call was detected. The framework may still serve routes from unparsed configuration.\n")
        parts.append("\nMiddleware, validation, background jobs, and uploads are not listed unless a known library (for example cors, joi, celery, multer) appears in the used-dependency list.\n")

    parts.append("\n## 6. API integration\n")
    parts.append("### Declarations inside this repository\n")
    parts.append("These are route-like strings in source. They are candidate APIs developed in this repo, not a verified OpenAPI document.\n\n")
    parts.append(_bullet([
        f"`{route['method']} {route['path']}` — `{route['file']}:{route['line']}`"
        for route in analysis["routes"][:40]
    ]) if analysis["routes"] else "- None detected.\n")
    parts.append("\n### URL literals that point outside the file\n")
    parts.append("These are strings in source. Presence of a URL is not proof of a successful integration or of a particular request schema.\n\n")
    parts.append(_bullet([
        f"`{item['url']}` referenced from `{item['file']}:{item['line']}`"
        for item in analysis["external_urls"]
    ]) if analysis["external_urls"] else "- None detected.\n")
    parts.append("\n### Other protocols\n")
    parts.append(_bullet([
        f"`{note['file']}:{note['line']}` — `{note['text']}`"
        for note in analysis["protocols"]
    ]) if analysis["protocols"] else "- No GraphQL or WebSocket literal was detected.\n")
    parts.append("\nRequest and response bodies were not executed, so schemas are not claimed. Authentication on an external call is claimed only when a security finding or an auth library import is in the same project; inspect the cited file before calling it authenticated.\n")

    parts.append("\n## 7. Database and data management\n")
    db_used = _used(analysis["database_dependencies"])
    if not db_used and not analysis["db_notes"] and not analysis["schema_files"]:
        parts.append("No database library, schema file, or database-related line was found in the scanned source.\n")
    else:
        parts.append(_bullet([_dep_line(dep) for dep in db_used]) if db_used else "- No database dependency import was matched to a manifest.\n")
        parts.append("\n### Schema or model files\n")
        parts.append(_bullet([f"`{path}`" for path in analysis["schema_files"]]) if analysis["schema_files"] else "- None found by filename.\n")
        parts.append("\n### Lines that mention data access\n")
        parts.append(_bullet([
            f"`{note['file']}:{note['line']}` — `{note['text']}`"
            for note in analysis["db_notes"][:20]
        ]) if analysis["db_notes"] else "- None.\n")
        parts.append("\nRelationships, indexes, and CRUD completeness are not claimed beyond the lines above. If those lines do not show a foreign key, relation, or index, this report does not invent one.\n")

    parts.append("\n## 8. AI/ML analysis\n")
    ml_used = _used(analysis["ml_dependencies"])
    if not ml_used and not analysis["ml_notes"]:
        parts.append("Not applicable. No machine learning library import or training-related line was found.\n")
    else:
        parts.append(_bullet([_dep_line(dep) for dep in ml_used]) if ml_used else "- Library names appeared in source lines but were not matched to a manifest.\n")
        parts.append("\n")
        parts.append(_bullet([f"`{note['file']}:{note['line']}` — `{note['text']}`" for note in analysis["ml_notes"][:20]]))
        joined = " ".join(note["text"].lower() for note in analysis["ml_notes"])
        if "from_pretrained" in joined:
            parts.append("\n`from_pretrained` appears, which means a published model is loaded. That is not evidence the candidate trained it.\n")
        if ".fit(" in joined or "fit(" in joined:
            parts.append("\nA `.fit(` call appears. That is evidence of a training or estimator fit call in that file, not evidence of a custom architecture.\n")
        if "from_pretrained" not in joined and ".fit(" not in joined and "fit(" not in joined:
            parts.append("\nThe scan found imports or names only. No training loop or `from_pretrained` call was identified, so the model should be treated as imported unless the cited file shows otherwise.\n")

    parts.append("\n## 9. Tools and development environment\n")
    parts.append(_bullet([f"`{path}`" for path in analysis["tool_files"]]) if analysis["tool_files"] else "- No Dockerfile, CI workflow, or common deploy manifest was found.\n")
    scripts = (analysis.get("package") or {}).get("scripts") or []
    if scripts:
        parts.append(f"\nRoot package scripts: {', '.join(scripts)}.\n")
    parts.append("\nGit is the version control system when a `.git` directory was present. An editor folder such as `.vscode` only means shared editor settings are in the repo, not that every author uses that editor.\n")
    parts.append(f"Test files found by path: {analysis['test_file_count']}.\n")
    if analysis["submodules"]:
        parts.append("\nSubmodule URLs listed in `.gitmodules` (contents were not cloned separately):\n")
        parts.append(_bullet(analysis["submodules"]))

    parts.append("\n## 10. Authentication and security\n")
    auth_names = [dep["name"] for dep in used if dep["name"].lower() in {"jsonwebtoken", "pyjwt", "bcrypt", "bcryptjs", "passlib", "passport", "cors", "helmet"}]
    if auth_names:
        parts.append("Auth-related libraries that are imported:\n")
        parts.append(_bullet(auth_names))
    else:
        parts.append("No JWT, password-hashing, Passport, CORS, or Helmet import was matched.\n")
    if analysis["committed_env_files"]:
        parts.append("\nEnvironment files whose contents were **not** copied into this report:\n")
        parts.append(_bullet([f"`{path}`" for path in analysis["committed_env_files"]]))
        parts.append("\nA committed `.env` or credential file is a handling risk even though the values are omitted here.\n")
    if analysis["security_findings"]:
        parts.append("\nLines that look like hardcoded secrets (values withheld):\n")
        parts.append(_bullet([
            f"`{item['kind']}` at `{item['file']}:{item['line']}`"
            for item in analysis["security_findings"]
        ]))
    else:
        parts.append("\nNo hardcoded-secret pattern was confirmed in the scanned lines. This is not a security audit.\n")
    parts.append("\nInput sanitization and CORS policy are not described beyond the libraries and files cited above.\n")

    parts.append("\n## 11. Project architecture and workflow\n")
    parts.append("Directory sample:\n\n```text\n" + analysis["tree"] + "\n```\n")
    parts.append(_mermaid(analysis))
    parts.append("\nData flow is described only where one scanned file contains both ends, for example a route file that also contains a database call or an external URL. Otherwise the pieces are listed as coexisting, not as a proven pipeline.\n")
    deploy = [path for path in analysis["tool_files"] if PathName(path)]
    parts.append("\nDeployment files are listed in section 14.\n")

    parts.append("\n## 12. Candidate contribution analysis\n")
    parts.append("Owning the GitHub repository does not show that this person wrote the code.\n\n")
    parts.append("### 1. Verified implementation\n")
    parts.append("The files and symbols in this report exist in the revision that was scanned. That verifies presence, not authorship.\n")
    parts.append("### 2. Evidence suggesting the profile owner contributed\n")
    if history.get("available"):
        parts.append(
            f"The fetched git history contains {history['total_commits']} commits from {history['author_count']} "
            f"{'author' if history['author_count'] == 1 else 'authors'}. "
            f"Commits whose author name or noreply email matches the URL owner `{source['owner']}`: {history['owner_hint_commits']}. "
            "A match is a hint, not proof, because git author fields can be anything.\n\n"
        )
        parts.append(_bullet([
            f"{row['name']} <{row['email']}> — {row['commits']} commits, +{row['added']}/-{row['deleted']}"
            f"{', owner-hint match' if row['matches_owner_hint'] else ''}"
            for row in history["authors"]
        ]))
    else:
        parts.append(history.get("reason") or "History unavailable.")
        parts.append("\n")
    if github.get("fork"):
        parts.append(f"\nThis repository is a fork of `{github.get('parent') or 'an unknown parent'}`. Code that predates the fork was not separated by this scan.\n")
    parts.append("\n### 3. Third-party or pre-existing implementation\n")
    parts.append(_bullet([f"`{item['path']}` — {item['reason']}" for item in analysis["generated_files"][:25]]) if analysis["generated_files"] else "- No lockfile or generated-file header was identified.\n")
    parts.append("\nManifest dependencies are third-party packages even when this repository imports them.\n")
    parts.append("\n### 4. Unverifiable ownership\n")
    if not history.get("available"):
        parts.append("Every file's author is unverified because commit history could not be read.\n")
    elif history["author_count"] > 1:
        parts.append("More than one git author appears, so files cannot be assigned to the profile owner without a per-file blame, which this report does not treat as identity proof.\n")
    else:
        parts.append("A single git author appears in the fetched history. That still does not prove the GitHub account owner wrote the code, because the author field may not be that account.\n")

    parts.append("\n## 13. Code quality and engineering practices\n")
    parts.append(f"- Test files detected by path: {analysis['test_file_count']}. Coverage percentage was not measured because no coverage artifact was parsed.\n")
    parts.append(f"- TODO or FIXME markers in scanned files: {analysis['todo_count']}.\n")
    parts.append(f"- Scanned files that mention try/catch: {analysis['files_with_error_handling']}.\n")
    parts.append(f"- Scanned files that mention an HTTP client call: {analysis['files_with_http_calls']}.\n")
    if analysis["large_files"]:
        parts.append("- Files over 400 lines among those read:\n")
        parts.append(_bullet([f"`{item['path']}` — {item['lines']} lines" for item in analysis["large_files"]]))
    else:
        parts.append("- No scanned source file exceeded 400 lines.\n")
    if readme["path"]:
        parts.append(f"- Documentation: `{readme['path']}` is present ({len(readme['text'])} characters were stored, capped).\n")
    else:
        parts.append("- Documentation: no README was found.\n")
    parts.append("- Naming quality and design-pattern purity were not scored. Those judgments need a human reading.\n")
    parts.append("- Maintainability inference: unused declared dependencies and files over 400 lines are the concrete debt signals this scan can support.\n")

    parts.append("\n## 14. Deployment and infrastructure\n")
    deploy_files = [
        path for path in analysis["tool_files"]
        if any(token in path.lower() for token in ("docker", "workflow", "vercel", "render", "fly.toml", "procfile", "netlify", "serverless", "cloudbuild", "app.yaml"))
    ]
    if deploy_files:
        parts.append(_bullet([f"`{path}`" for path in deploy_files]))
        parts.append("\nThe scan did not deploy the project, so production-versus-development behavior is only whatever those files themselves contain.\n")
    else:
        parts.append("No Dockerfile, compose file, GitHub Actions workflow, or common host manifest (Vercel, Render, Fly, Procfile, Netlify, Serverless, Cloud Build) was found.\n")
    if analysis["committed_env_files"]:
        parts.append("\nEnvironment files are present in the tree. Values were not copied. Prefer a host secret store over committed env files.\n")

    parts.append("\n## 15. Technical skill mapping\n")
    parts.append("Confidence is about the evidence, not about the candidate's mastery. High means an import or declaration was found in a file. Low means the signal is only a filename or a README topic.\n\n")
    skills = _skills(analysis)
    if not skills:
        parts.append("No skill row met the evidence bar.\n")
    for skill in skills:
        parts.append(
            f"- **{skill['category']} / {skill['skill']}** — {skill['complexity']} complexity signal, {skill['confidence']} confidence. "
            f"{skill['evidence']} Files: {', '.join(f'`{path}`' for path in skill['files'][:6])}.\n"
        )

    parts.append("\n## 16. Interview questions\n")
    parts.append("Questions are tied to files from this scan. Expected answers describe what the candidate should be able to explain. They are not a hidden solution key, because the scan does not execute the program.\n\n")
    for question in _questions(analysis):
        parts.append(_question_markdown(question))
        parts.append("\n")

    parts.append("## 17. Final repository assessment\n")
    parts.append(f"1. **Project summary.** {title}. {description or 'No short description was found.'}\n")
    stack = ", ".join(dep["name"] for dep in used[:20]) or "no imported dependencies matched"
    parts.append(f"2. **Technology stack in use.** {stack}.\n")
    parts.append(f"3. **Languages.** Primary: {primary or 'not identified'}. Others are listed in section 2.\n")
    parts.append(f"4. **Frontend and backend.** Frontend library imports: {', '.join(dep['name'] for dep in front_used) or 'none'}. Backend library imports: {', '.join(dep['name'] for dep in back_used) or 'none'}. Route declarations found: {len(analysis['routes'])}.\n")
    parts.append(f"5. **APIs.** Internal route-like declarations: {len(analysis['routes'])}. External URL literals: {len(analysis['external_urls'])}.\n")
    parts.append(f"6. **Databases.** {', '.join(dep['name'] for dep in db_used) or 'no imported database library'}.\n")
    parts.append(f"7. **AI/ML.** {'See section 8.' if ml_used or analysis['ml_notes'] else 'None identified.'}\n")
    parts.append(f"8. **Tools and infrastructure.** {', '.join(deploy_files) if deploy_files else 'No deployment manifest identified.'}\n")
    if history.get("available"):
        parts.append(f"9. **Contribution evidence.** {history['owner_hint_commits']} of {history['total_commits']} fetched commits match the owner hint. Authors: {history['author_count']}.\n")
    else:
        parts.append("9. **Contribution evidence.** Commit history was not available. Authorship is unverified.\n")
    strengths = []
    if analysis["test_file_count"]:
        strengths.append(f"{analysis['test_file_count']} test files")
    if readme["path"]:
        strengths.append("a README is present")
    if deploy_files:
        strengths.append("deployment or CI configuration is present")
    if used:
        strengths.append("dependencies that are actually imported")
    parts.append("10. **Strengths with evidence.** " + ("; ".join(strengths) if strengths else "The scan did not find tests, a README, CI, and imported dependencies together.") + ".\n")
    gaps = []
    if not analysis["test_file_count"]:
        gaps.append("no test files were found by path")
    if unused:
        gaps.append(f"{len(unused)} dependencies are declared but not imported in scanned source")
    if analysis["committed_env_files"]:
        gaps.append("an environment or credential file is committed")
    if not readme["path"]:
        gaps.append("no README")
    parts.append("11. **Possible gaps.** " + ("; ".join(gaps) if gaps else "No automatic gap rule fired. This does not mean the project is complete.") + ".\n")
    parts.append(f"12. **Code quality.** See section 13. Large scanned files: {len(analysis['large_files'])}. TODO/FIXME count: {analysis['todo_count']}.\n")
    parts.append(f"13. **Security and scale.** Secret-like lines withheld from the report: {len(analysis['security_findings'])}. Committed env files: {len(analysis['committed_env_files'])}. Scale is not documented by the repository.\n")
    parts.append(f"14. **Interview questions.** {len(_questions(analysis))} questions are written in section 16.\n")
    parts.append("15. **Overall technical complexity.** " + complexity + ". " + " ".join(complexity_reasons) + "\n")
    return "\n".join(parts)


def PathName(path: str) -> bool:
    return True


def _skills(analysis: dict) -> list[dict]:
    rows = []
    if analysis.get("primary_language"):
        sample = next((lang for lang in analysis["languages"] if lang["name"] == analysis["primary_language"]), None)
        rows.append({
            "category": "Programming languages",
            "skill": analysis["primary_language"],
            "evidence": "Largest programming language by file bytes.",
            "files": (sample or {}).get("sample_files") or [],
            "complexity": "Moderate" if sample and sample["bytes"] > 20_000 else "Low",
            "confidence": "High",
        })
    for dep in _used(analysis["frontend_dependencies"]):
        rows.append({
            "category": "Frontend development",
            "skill": dep["name"],
            "evidence": "Imported from a parsed manifest dependency.",
            "files": dep["used_in"],
            "complexity": "Moderate" if len(dep["used_in"]) > 2 else "Low",
            "confidence": "High",
        })
    for dep in _used(analysis["backend_dependencies"]):
        rows.append({
            "category": "Backend development",
            "skill": dep["name"],
            "evidence": "Imported from a parsed manifest dependency.",
            "files": dep["used_in"],
            "complexity": "Moderate" if analysis["routes"] else "Low",
            "confidence": "High",
        })
    for dep in _used(analysis["database_dependencies"]):
        rows.append({
            "category": "Database management",
            "skill": dep["name"],
            "evidence": "Imported from a parsed manifest dependency.",
            "files": dep["used_in"],
            "complexity": "Moderate" if analysis["db_notes"] else "Low",
            "confidence": "High",
        })
    if analysis["routes"]:
        rows.append({
            "category": "API development and integration",
            "skill": "Route handlers",
            "evidence": f"{len(analysis['routes'])} route-like declarations.",
            "files": sorted({route["file"] for route in analysis["routes"]}),
            "complexity": "Moderate" if len(analysis["routes"]) >= 3 else "Low",
            "confidence": "Medium",
        })
    for dep in _used(analysis["ml_dependencies"]):
        rows.append({
            "category": "AI/ML",
            "skill": dep["name"],
            "evidence": "Imported from a parsed manifest dependency.",
            "files": dep["used_in"],
            "complexity": "High" if any("fit(" in note["text"] for note in analysis["ml_notes"]) else "Moderate",
            "confidence": "High",
        })
    deploy = [path for path in analysis["tool_files"] if "docker" in path.lower() or "workflow" in path.lower()]
    if deploy:
        rows.append({
            "category": "DevOps and cloud",
            "skill": "Containers or CI config",
            "evidence": "Deployment or workflow files are in the tree.",
            "files": deploy,
            "complexity": "Low",
            "confidence": "Medium",
        })
    if analysis["security_findings"] or any(dep["name"].lower() in {"bcrypt", "jsonwebtoken", "pyjwt", "passlib"} for dep in _used(analysis["dependencies"])):
        rows.append({
            "category": "Cybersecurity",
            "skill": "Auth library or secret handling",
            "evidence": "An auth library is imported, or a secret-like line was detected and withheld.",
            "files": [dep["used_in"][0] for dep in _used(analysis["dependencies"]) if dep["used_in"] and dep["name"].lower() in {"bcrypt", "jsonwebtoken", "pyjwt", "passlib"}] or [analysis["security_findings"][0]["file"]],
            "complexity": "Moderate",
            "confidence": "Medium",
        })
    if analysis["test_file_count"]:
        rows.append({
            "category": "Software engineering",
            "skill": "Automated tests",
            "evidence": "Files whose paths look like tests.",
            "files": analysis["test_files"][:8],
            "complexity": "Low",
            "confidence": "Medium",
        })
    if analysis["tool_files"]:
        rows.append({
            "category": "Tools and platforms",
            "skill": "Repository tooling",
            "evidence": "Tooling or editor configuration files.",
            "files": analysis["tool_files"][:8],
            "complexity": "Low",
            "confidence": "Medium",
        })
    return rows
