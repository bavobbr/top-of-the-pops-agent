"""Gemini AI integration for the Top of the Pops app."""

import os
import json
import json5
import re
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_AI_STUDIO_KEY'))

# Schema for category suggestions
SUGGESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["suggestions"]
}

# Schema for generating a list of items
LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "string"}
        },
        "properties": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["items", "properties"]
}

# Create models with specific schemas
model_suggestions = genai.GenerativeModel(
    'gemini-2.0-flash',
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": SUGGESTIONS_SCHEMA
    }
)

model_list = genai.GenerativeModel(
    'gemini-2.0-flash',
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": LIST_SCHEMA
    }
)

# Details model uses JSON mode without schema (dynamic properties)
model_details = genai.GenerativeModel(
    'gemini-2.0-flash',
    generation_config={
        "response_mime_type": "application/json"
    }
)


def parse_json_response(text):
    """Parse JSON response with fallback for malformed AI output.

    Handles common issues like unquoted string values (e.g., "9e eeuw").
    """
    # Try standard JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix unquoted values that contain letters (e.g., "9e eeuw", "circa 1500")
    fixed = text
    # Pass 1: Fix values ending with , } or ]
    fixed = re.sub(
        r':\s*(?!["\[\{])([^,}\]"\n]*[a-zA-Z][^,}\]"\n]*?)([,}\]])',
        r': "\1"\2',
        fixed
    )
    # Pass 2: Fix values at end of line before closing brace
    fixed = re.sub(
        r':\s*(?!["\[\{])([^,}\]"\n]*[a-zA-Z][^,}\]"\n]*?)\s*\n(\s*[}\]])',
        r': "\1"\n\2',
        fixed
    )

    # Try parsing fixed JSON
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        # Last resort: use json5 which is more lenient
        return json5.loads(fixed)


def generate_suggestions():
    """Generate quiz category suggestions."""
    prompt = """Generate 20 diverse and interesting quiz category suggestions for a "top items" learning app.

Include a mix of:
- Broad categories (e.g., "movie stars", "car brands")
- Time-specific categories (e.g., "80s rock bands", "2010s pop stars")
- Niche/specific categories (e.g., "TikTok stars from 2020", "French impressionist painters")
- Geographic categories (e.g., "Japanese video game companies", "British monarchs")
- Achievement-based (e.g., "Nobel Prize winners in Physics", "Olympic gold medalists in swimming")

Return a JSON object with:
- "suggestions": An array of exactly 20 strings, each being a quiz category

Make them fun, educational, and varied. Keep each suggestion concise (2-6 words).
Return ONLY the JSON object, no markdown."""

    response = model_suggestions.generate_content(prompt)
    return json.loads(response.text)


def generate_item_list(category, count, language_instruction):
    """Generate a ranked list of items for a category."""
    prompt = f"""You are helping create a study guide. The user wants to learn the top {count} {category}.

Return a JSON object with exactly these two fields:
1. "items": An array of exactly {count} strings (just names, no objects), ranked from most notable/important to least
2. "properties": An array of 3-5 property names as strings, using snake_case

For properties, include:
- Basic facts (birth_date, founded_year, country, etc.)
- At least ONE list-type property that shows notable works/achievements (e.g., notable_movies, top_songs, famous_works, popular_models, key_inventions, championship_wins)

Examples by category:
- movie stars: ["birth_date", "nationality", "notable_movies", "awards_won"]
- bands: ["formed_year", "genre", "top_songs", "members"]
- car brands: ["founded_year", "country", "popular_models", "known_for"]

Be factual and use commonly accepted rankings. Return ONLY the JSON object, no markdown or other text.{language_instruction}"""

    response = model_list.generate_content(prompt)
    return json.loads(response.text)


def generate_item_details(item, category, properties, language, language_instruction):
    """Generate details for a specific item."""
    properties_str = ', '.join(properties) if properties else 'relevant characteristics'

    # For non-English languages, request English equivalents for image search
    english_fields_instruction = ""
    if language != 'en':
        english_fields_instruction = """
- "english_name": The standard English name for this item (for image lookup)
- "english_category": The English translation of the category context"""

    prompt = f"""Provide details about "{item}" in the context of {category}.

Return a JSON object with:
- "name": Full/official name
- "description": 2-3 sentence summary
- "properties": Object with values for each of: {properties_str}{english_fields_instruction}

IMPORTANT JSON RULES:
1. ALL string values MUST be in double quotes, including dates, years, and descriptions
2. For properties with multiple items (like notable_works, top_songs), use JSON arrays: ["Item 1", "Item 2", "Item 3"]
3. Never use unquoted values - even "9th century" must be "9th century" in quotes

Be concise and factual. Return ONLY valid JSON.{language_instruction}"""

    response = model_details.generate_content(prompt)
    return parse_json_response(response.text)
