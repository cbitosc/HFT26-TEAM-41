"""Keyword maps for the profiler's rules. Plain data: edit here, not in the code.

A term matches case-insensitively as a whole word or phrase in any portfolio text.
`term*` also matches longer words that start with it (paginat* -> pagination, paginated).
`=term` matches only a whole stack item (a project keyword, skill keyword or skill name),
for short words that are ambiguous in prose (=go).
"""

RUNTIMES: dict[str, list[str]] = {
    "python311": [
        "python", "django", "flask", "fastapi", "pandas", "numpy", "pytorch", "tensorflow",
        "keras", "scikit-learn", "sklearn", "celery", "pytest", "sqlalchemy", "pydantic",
        "jupyter",
    ],
    "node20": [
        "javascript", "typescript", "node.js", "nodejs", "=node", "react*", "next.js",
        "nextjs", "express", "express.js", "nestjs", "vue*", "angular", "svelte*", "jest",
        "npm",
    ],
}  # fmt: skip

# Stacks without a runtime image. Reported in unsupported_notes; the closest runtime is
# chosen by domain (CLOSEST_RUNTIME).
UNSUPPORTED_STACKS: dict[str, list[str]] = {
    "Go": ["golang", "=go", "gin", "grpc-go"],
    "Java": ["java", "spring", "spring boot", "maven", "gradle"],
    "Kotlin": ["kotlin", "ktor"],
    "C#/.NET": ["c#", ".net", "asp.net", "dotnet"],
    "Ruby": ["ruby", "rails", "ruby on rails"],
    "PHP": ["php", "laravel", "symfony"],
    "Rust": ["rust", "actix", "tokio"],
    "C/C++": ["c++", "=cpp", "=c"],
    "Swift": ["swift", "swiftui"],
    "Scala": ["scala"],
    "Elixir": ["elixir", "phoenix"],
    "Dart/Flutter": ["dart", "flutter"],
}

CLOSEST_RUNTIME = {
    "backend": "python311",
    "web": "node20",
    "ml": "python311",
    "security": "python311",
}

DOMAINS: dict[str, list[str]] = {
    "backend": [
        "backend", "back-end", "rest api*", "restful", "api*", "graphql", "grpc", "microservice*",
        "server-side", "fastapi", "django", "flask", "express", "nestjs", "spring", "postgres*",
        "mysql", "sqlite", "sql", "database*", "celery", "background job*", "kafka", "rabbitmq",
        "redis",
    ],
    "web": [
        "frontend", "front-end", "web app*", "single-page", "react*", "next.js", "nextjs",
        "vue*", "angular", "svelte*", "redux", "css", "html", "tailwind*", "vite", "webpack",
        "ui", "ux", "responsive",
    ],
    "ml": [
        "machine learning", "=ml", "deep learning", "neural network*", "pytorch", "tensorflow",
        "keras", "scikit-learn", "sklearn", "xgboost", "pandas", "numpy", "jupyter", "nlp",
        "computer vision", "hugging face", "huggingface", "transformers", "data science",
        "model training", "fine-tun*", "llm*", "classifier*",
    ],
    "security": [
        "security", "cybersecurity", "pentest*", "penetration test*", "owasp", "vulnerabilit*",
        "ctf", "cryptograph*", "burp*", "nmap", "metasploit", "wireshark", "exploit*", "xss",
        "csrf", "sql injection", "threat*", "siem", "forensic*", "malware", "red team",
        "blue team", "bug bount*", "intrusion detection", "hardening",
    ],
}  # fmt: skip

# Domain-task concepts. Only those in the seed vocabulary (seeds/*/concepts.yaml) are used;
# the concept's own name always matches too.
CONCEPTS: dict[str, list[str]] = {
    "pagination": ["paginat*", "infinite scroll*", "cursor-based", "page size"],
    "filtering": ["filter*", "search*", "faceted"],
    "sorting": ["sort*", "order by", "ranking"],
    "auth": [
        "auth", "authn", "authz", "authenticat*", "authoriz*", "login*", "sign-in", "sign in",
        "jwt", "oauth*", "rbac", "access control", "permission*", "api key*",
    ],
    "validation": ["validat*", "pydantic", "zod", "joi", "marshmallow", "sanitiz*"],
    "caching": ["cach*", "redis", "memcached", "memoiz*"],
    "reporting": ["report*", "analytics", "dashboard*", "aggregat*", "csv export*"],
    "importing": [
        "bulk import*", "batch import*", "csv import*", "data import*", "ingest*", "dedup*",
        "de-dup*", "etl",
    ],
}  # fmt: skip
