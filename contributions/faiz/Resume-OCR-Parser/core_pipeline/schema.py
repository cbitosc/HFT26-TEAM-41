# core_pipeline/schema.py

# Define the comprehensive JSON schema for the structured resume data.
# This schema is designed to handle multiple entries for experience, education, projects, etc.,
# and categorize skills, plus fields for declaration and links.
# To adapt for different industries, modify this schema.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "personal_info": {
            "type": "OBJECT",
            "properties": {
                "name": { "type": "STRING" },
                "email": { "type": "STRING" },
                "phone": { "type": "STRING" },
                "linkedin": { "type": "STRING" },
                "github": { "type": "STRING" },
                "portfolio": { "type": "STRING" },
                "address": { "type": "STRING" }
            },
            "propertyOrdering": ["name", "email", "phone", "linkedin", "github", "portfolio", "address"]
        },
        "summary_objective": { "type": "STRING" },
        "experience": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": { "type": "STRING" },
                    "company": { "type": "STRING" },
                    "location": { "type": "STRING" },
                    "start_date": { "type": "STRING" },
                    "end_date": { "type": "STRING" },
                    "description": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    }
                },
                "propertyOrdering": ["title", "company", "location", "start_date", "end_date", "description"]
            }
        },
        "education": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "degree": { "type": "STRING" },
                    "major": { "type": "STRING" },
                    "institution": { "type": "STRING" },
                    "location": { "type": "STRING" },
                    "start_date": { "type": "STRING" },
                    "end_date": { "type": "STRING" },
                    "gpa": { "type": "STRING" },
                    "description": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    }
                },
                "propertyOrdering": ["degree", "major", "institution", "location", "start_date", "end_date", "gpa", "description"]
            }
        },
        "skills": {
            "type": "OBJECT",
            "properties": {
                "programming_languages": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                },
                "frameworks_libraries": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                },
                "databases": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                },
                "tools_technologies": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                },
                "soft_skills": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                },
                "other_skills": {
                    "type": "ARRAY",
                    "items": { "type": "STRING" }
                }
            },
            "propertyOrdering": [
                "programming_languages", "frameworks_libraries", "databases",
                "tools_technologies", "soft_skills", "other_skills"
            ]
        },
        "projects": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": { "type": "STRING" },
                    "link": { "type": "STRING" },
                    "description": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    }
                },
                "propertyOrdering": ["name", "link", "description"]
            }
        },
        "awards_certifications": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": { "type": "STRING" },
                    "issuer": { "type": "STRING" },
                    "date": { "type": "STRING" }
                },
                "propertyOrdering": ["name", "issuer", "date"]
            }
        },
        "publications": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "authors": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "journal_conference": {"type": "STRING"},
                    "date": {"type": "STRING"},
                    "link": {"type": "STRING"},
                    "abstract": {"type": "STRING"}
                },
                "propertyOrdering": ["title", "authors", "journal_conference", "date", "link", "abstract"]
            }
        },
        "references": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "contact": {"type": "STRING"},
                    "relationship": {"type": "STRING"}
                },
                "propertyOrdering": ["name", "contact", "relationship"]
            }
        },
        "languages": {
            "type": "ARRAY",
            "items": { "type": "STRING" }
        },
        "interests": {
            "type": "ARRAY",
            "items": { "type": "STRING" }
        },
        "declaration": { "type": "STRING" },
        "links": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "text": { "type": "STRING" },
                    "url": { "type": "STRING" }
                },
                "propertyOrdering": ["text", "url"]
            }
        }
    },
    "propertyOrdering": [
        "personal_info",
        "summary_objective",
        "experience",
        "education",
        "skills",
        "projects",
        "awards_certifications",
        "publications",
        "references",
        "languages",
        "interests",
        "declaration",
        "links"
    ]
}