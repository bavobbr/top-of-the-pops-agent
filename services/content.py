"""Content processing: markdown rendering and language support."""

import re
import markdown
import bleach

# Allowed HTML tags and attributes for sanitized markdown output
ALLOWED_TAGS = ['p', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'br']
ALLOWED_ATTRIBUTES = {}

# Supported languages for AI responses
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'zh': 'Chinese (Simplified)',
    'hi': 'Hindi',
    'es': 'Spanish',
    'fr': 'French',
    'ar': 'Arabic',
    'bn': 'Bengali',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'de': 'German',
    'ko': 'Korean',
    'vi': 'Vietnamese',
    'it': 'Italian',
    'tr': 'Turkish',
    'pl': 'Polish',
    'nl': 'Dutch',
    'th': 'Thai',
    'id': 'Indonesian',
    'sv': 'Swedish',
}


def get_language_instruction(language_code):
    """Get prompt instruction for responding in a specific language."""
    if language_code == 'en' or language_code not in SUPPORTED_LANGUAGES:
        return ''
    language_name = SUPPORTED_LANGUAGES[language_code]
    return f'\n\nIMPORTANT: The user input may be in {language_name}. Interpret it in that language and respond with all text content (items, descriptions, property values) in {language_name}. Property keys should remain in English snake_case.'


def render_markdown(text, inline=False):
    """Convert markdown to sanitized HTML.

    Args:
        text: The markdown text to render
        inline: If True, strip wrapping <p> tags for inline use (e.g., list items)
    """
    if not text:
        return ''
    # Convert markdown to HTML
    html = markdown.markdown(str(text))
    # Sanitize to only allow safe tags
    clean_html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    # Strip wrapping <p> tags for inline content
    if inline:
        clean_html = re.sub(r'^<p>(.*)</p>$', r'\1', clean_html.strip(), flags=re.DOTALL)
    return clean_html


def render_markdown_in_result(result):
    """Apply markdown rendering to description and properties in a result dict."""
    if 'description' in result:
        result['description'] = render_markdown(result['description'])

    if 'properties' in result and isinstance(result['properties'], dict):
        for key, value in result['properties'].items():
            if isinstance(value, list):
                # Use inline=True for list items to avoid <p> wrapper
                result['properties'][key] = [render_markdown(item, inline=True) for item in value]
            elif isinstance(value, str):
                # Use inline=True for single values
                result['properties'][key] = render_markdown(value, inline=True)

    return result
