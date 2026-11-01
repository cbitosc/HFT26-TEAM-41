# core_pipeline/parser.py

import json
import requests
import os
from typing import List, Dict, Union, Optional
from urllib.parse import urlparse, urlunparse

from core_pipeline.schema import RESPONSE_SCHEMA

def normalize_url(url: str) -> str:
    """
    Normalizes a URL for consistent comparison.
    Adds 'https://' if no scheme is present, removes trailing slashes,
    and converts to lowercase.
    """
    if not url:
        return ""

    if url.lower().startswith("mailto:"):
        return url.lower()

    if not urlparse(url).scheme:
        url = "https://" + url
    parsed = urlparse(url)

    path = parsed.path.rstrip('/') if parsed.path != '/' else parsed.path

    normalized_url = urlunparse(parsed._replace(path=path, query="", fragment=""))
    return normalized_url.lower()

def clean_description_arrays(data: dict) -> dict:
    """
    Recursively cleans 'description' arrays in experience and education sections
    to ensure they only contain strings, not objects.
    Discards non-string items that are not clearly descriptive text.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ["experience", "education"] and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "description" in item and isinstance(item["description"], list):
                        cleaned_descriptions = []
                        for desc_item in item["description"]:
                            if isinstance(desc_item, str):
                                cleaned_descriptions.append(desc_item)
                            elif isinstance(desc_item, dict):
                                # Prioritize common keys for descriptive text
                                if "declaration" in desc_item and isinstance(desc_item["declaration"], str):
                                    cleaned_descriptions.append(desc_item["declaration"])
                                elif "text" in desc_item and isinstance(desc_item["text"], str) and desc_item["text"]:
                                    cleaned_descriptions.append(desc_item["text"])
                                elif "description" in desc_item and isinstance(desc_item["description"], str) and desc_item["description"]:
                                    cleaned_descriptions.append(desc_item["description"])
                                # If an object is found but doesn't contain a clear descriptive string,
                                # it will be skipped (effectively discarded).
                        item["description"] = cleaned_descriptions
            else:
                clean_description_arrays(value) # Recurse for other nested dictionaries
    elif isinstance(data, list):
        for item in data:
            clean_description_arrays(item)
    return data


def parse_resume_with_gemini(
    api_key: str,
    text_input: Optional[str] = None,
    image_parts: Optional[List[Dict[str, str]]] = None,
    extracted_pdf_links: Optional[List[Dict[str, str]]] = None
) -> dict:
    """
    Parses resume data using the Gemini API and applies post-processing.

    Args:
        api_key: Your Gemini API key.
        text_input: Raw text content of the resume.
        image_parts: List of dictionaries with base64 image data for Gemini's multimodal input.
        extracted_pdf_links: List of links explicitly extracted from PDF annotations.

    Returns:
        A dictionary containing the structured resume data, or an error message.
    """
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    gemini_contents: List[Dict[str, Union[str, Dict]]] = []

    # Base prompt instructions, common for all input types
    base_prompt_instructions = """
        Instructions for Extraction:
        1.  **Strict Schema Adherence:** Your output MUST strictly follow the provided JSON schema. Do not deviate from the field names or types.
        2.  **Complete and Valid JSON:** Ensure the entire output is a single, complete, and syntactically valid JSON object. Do not truncate the JSON or include any non-JSON text.
        3.  **Completeness:** If a field is not explicitly present in the resume, provide an empty string ("") for string fields, an empty array ([]) for array fields, or an empty object ({}) for object fields. DO NOT omit any fields defined in the schema.
        4.  **Experience/Education Description:** For 'description' fields within 'experience' and 'education' sections, break down bullet points or distinct sentences into separate items within the array. Each item in the 'description' array MUST be a string. Do NOT put objects inside the 'description' array.
        5.  **Dates:** Extract 'start_date' and 'end_date' for experiences and education. If only a single date is available (e.g., for a certification or a current role), use the most appropriate date field (e.g., 'date' for awards, 'start_date' for current roles with no end date, leaving 'end_date' empty).
        6.  **Skills Categorization:** Categorize skills into the specified sub-categories (programming_languages, frameworks_libraries, databases, tools_technologies, soft_skills, other_skills). If a skill doesn't fit a specific category, place it in 'other_skills'.
        7.  **URLs & Links:** Identify and extract all URLs.
            * **Primary Mapping:** For links clearly associated with "LinkedIn", "GitHub", "Portfolio", or "Email" (either by explicit text or strong contextual cues), populate the corresponding `personal_info` fields (`personal_info.linkedin`, `personal_info.github`, `personal_info.portfolio`, `personal_info.email`).
            * **General Links:** For any other links (e.g., project links, blog links), populate the `links` array.
            * **CRITICAL for `links` array items:**
                * The `text` field MUST contain the *exact descriptive label* associated with the URL (e.g., 'Hugging Face', 'My Blog', 'Project Demo'). **Even if the text is a common identifier like 'LinkedIn' or 'GitHub', if it's explicitly linked, it should be the `text` value.**
                * ONLY if there is absolutely no descriptive label, and the visible text is *literally* the URL itself (e.g., 'https://example.com' is the visible text, and it links to 'https://example.com'), then the `text` field should be an empty string to avoid redundancy.
            * **Avoid Duplication:** If a URL is already assigned to a specific field in `personal_info` or within a `project.link`, DO NOT duplicate that same URL in the `links` array.
        8.  **Robustness:** Be highly robust to various resume templates, formatting styles, and content arrangements. Your goal is to consistently produce the structured data regardless of the input resume's visual layout.
        9.  **Arrays:** For fields that are arrays (e.g., 'experience', 'education', 'projects'), ensure each entry is a separate object within the array.
        10. **Summary/Objective:** Extract the main profile summary or objective statement.
        11. **Declaration:** Extract any declaration statement, if present.
        12. **Cross-reference:** If both text and image data are provided, cross-reference information between them for maximum accuracy and completeness. The image provides crucial layout and visual context, especially for visual links and overall structure.

        Please provide the output as a JSON object that conforms to the `responseSchema`.
    """

    # Add the main prompt text as the first part of the Gemini content list.
    gemini_contents.append({"text": f"You are a highly accurate and robust resume parser.\nExtract all relevant information from the provided resume and structure it strictly according to the JSON schema below.\n\n{base_prompt_instructions}"})

    # Add text input if available
    if text_input:
        gemini_contents.append({"text": f"Resume Text:\n{text_input}\n\n"})
    
    # Add image parts if available
    if image_parts:
        for part in image_parts:
            gemini_contents.append(part)

    payload = {
        "contents": [{"role": "user", "parts": gemini_contents}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        result = response.json()

        if result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and \
           result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:

            json_string = result["candidates"][0]["content"]["parts"][0].get("text")
            if json_string:
                try:
                    parsed_json = json.loads(json_string)
                    
                    # --- Post-processing to clean description arrays ---
                    parsed_json = clean_description_arrays(parsed_json)
                    # --- END Post-processing ---

                    if 'personal_info' not in parsed_json:
                        parsed_json['personal_info'] = {}

                    link_type_mapping = {
                        'linkedin.com': {'field': 'linkedin', 'texts': ['linkedin', 'linkedin profile']},
                        'github.com': {'field': 'github', 'texts': ['github']},
                        'mailto:': {'field': 'email', 'texts': ['email']},
                        'portfolio': {'field': 'portfolio', 'texts': ['portfolio', 'website', 'my website']},
                        'site': {'field': 'portfolio', 'texts': ['website', 'my website']},
                    }

                    
                    specific_urls = set()
                    for key in ['linkedin', 'github', 'portfolio', 'email']:
                        if key in parsed_json['personal_info'] and parsed_json['personal_info'][key]:
                            specific_urls.add(normalize_url(parsed_json['personal_info'][key]))
                    if 'email' in parsed_json['personal_info'] and parsed_json['personal_info']['email']:
                        specific_urls.add(normalize_url(f"mailto:{parsed_json['personal_info']['email']}"))

                    if 'projects' in parsed_json:
                        for project in parsed_json['projects']:
                            if 'link' in project and project['link']:
                                specific_urls.add(normalize_url(project['link']))

                    if 'links' not in parsed_json:
                        parsed_json['links'] = []

                    temp_general_links = []
                    for link_item in parsed_json['links']:
                        if 'url' in link_item and link_item['url']:
                            normalized_link_url = normalize_url(link_item['url'])
                            original_link_text = link_item.get('text', '').strip().lower()

                            moved_to_personal_info = False

                            for pattern, mapping_info in link_type_mapping.items():
                                if pattern in normalized_link_url:
                                    field_name = mapping_info['field']
                                    if not parsed_json['personal_info'].get(field_name):
                                        parsed_json['personal_info'][field_name] = link_item['url']
                                        specific_urls.add(normalized_link_url)
                                        moved_to_personal_info = True
                                        break
                            
                            if not moved_to_personal_info:
                                for pattern, mapping_info in link_type_mapping.items():
                                    if original_link_text in mapping_info['texts']:
                                        field_name = mapping_info['field']
                                        if not parsed_json['personal_info'].get(field_name):
                                            parsed_json['personal_info'][field_name] = link_item['url']
                                            specific_urls.add(normalized_link_url)
                                            moved_to_personal_info = True
                                            break

                            if not moved_to_personal_info:
                                if normalized_link_url not in specific_urls:
                                    if original_link_text == normalized_link_url: # Compare with normalized URL
                                        link_item['text'] = ""
                                    temp_general_links.append(link_item)
                                    specific_urls.add(normalized_link_url)

                    parsed_json['links'] = temp_general_links

                    if extracted_pdf_links:
                        for pdf_link in extracted_pdf_links:
                            if 'url' in pdf_link and pdf_link['url']:
                                normalized_pdf_url = normalize_url(pdf_link['url'])

                                moved_to_personal_info_from_pdf = False
                                for pattern, mapping_info in link_type_mapping.items():
                                    if pattern in normalized_pdf_url:
                                        field_name = mapping_info['field']
                                        if not parsed_json['personal_info'].get(field_name):
                                            parsed_json['personal_info'][field_name] = pdf_link['url']
                                            specific_urls.add(normalized_pdf_url)
                                            moved_to_personal_info_from_pdf = True
                                            break

                                if not moved_to_personal_info_from_pdf:
                                    if normalized_pdf_url not in specific_urls:
                                        parsed_json['links'].append(pdf_link)
                                        specific_urls.add(normalized_pdf_url)

                    return parsed_json
                except json.JSONDecodeError as e:
                    # Include the raw JSON string in the error for better debugging
                    return {"error": f"Failed to decode JSON from API response: {e}", "raw_response": json_string}
            else:
                return {"error": "API response text part is empty."}
        else:
            return {"error": "Unexpected API response structure.", "full_response": result}

    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}
