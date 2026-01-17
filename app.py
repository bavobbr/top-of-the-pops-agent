import os
import json
import json5
import uuid
import re
import time
from urllib.parse import urlparse
import requests
import markdown
import bleach
from flask import Flask, render_template, request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Rate limiting configuration
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://",
)

# Session management configuration
SESSION_EXPIRY_SECONDS = 3600  # 1 hour
MAX_SESSIONS_PER_IP = 5
MAX_TOTAL_SESSIONS = 1000
CLEANUP_INTERVAL = 100  # Run cleanup every N requests
request_counter = 0


@app.errorhandler(429)
def ratelimit_handler(e):
    """Return JSON error for rate limit exceeded."""
    return jsonify({
        'error': 'rate_limit_exceeded',
        'message': "You're going too fast! Please wait a moment before trying again.",
        'retry_after': e.description
    }), 429


@app.before_request
def check_origin():
    """Block cross-origin requests to API endpoints."""
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        # If Origin header is present, it's a cross-origin request
        if origin:
            # Extract hostname from origin (handles http/https differences)
            origin_host = urlparse(origin).netloc
            # Get the host from the request (handles Cloud Run proxy)
            request_host = request.host  # Just the host:port, no scheme
            if origin_host != request_host:
                return jsonify({
                    'error': 'forbidden',
                    'message': 'Cross-origin requests are not allowed'
                }), 403


@app.after_request
def set_security_headers(response):
    """Set security headers to prevent cross-origin access."""
    # Prevent embedding in iframes from other origins
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Enable XSS protection
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

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

# In-memory session storage
# Structure: {session_id: {'data': {...}, 'ip': '...', 'created_at': timestamp, 'last_access': timestamp}}
sessions = {}


def cleanup_sessions():
    """Remove expired sessions and enforce limits."""
    global sessions
    now = time.time()

    # Remove expired sessions
    expired = [sid for sid, s in sessions.items()
               if now - s['last_access'] > SESSION_EXPIRY_SECONDS]
    for sid in expired:
        del sessions[sid]

    # If still over limit, remove oldest sessions
    if len(sessions) > MAX_TOTAL_SESSIONS:
        sorted_sessions = sorted(sessions.items(), key=lambda x: x[1]['last_access'])
        to_remove = len(sessions) - MAX_TOTAL_SESSIONS
        for sid, _ in sorted_sessions[:to_remove]:
            del sessions[sid]


def get_session_data():
    """Get or create session data for current user."""
    global request_counter

    # Periodic cleanup
    request_counter += 1
    if request_counter >= CLEANUP_INTERVAL:
        request_counter = 0
        cleanup_sessions()

    client_ip = get_remote_address()
    now = time.time()

    if 'session_id' not in session:
        # Check if IP has too many sessions
        ip_sessions = [s for s in sessions.values() if s['ip'] == client_ip]
        if len(ip_sessions) >= MAX_SESSIONS_PER_IP:
            # Remove oldest session for this IP
            oldest = min(ip_sessions, key=lambda x: x['last_access'])
            oldest_id = next(sid for sid, s in sessions.items() if s is oldest)
            del sessions[oldest_id]

        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']

    if session_id not in sessions:
        sessions[session_id] = {
            'data': {
                'category': None,
                'items': [],
                'properties': [],
                'details_cache': {}
            },
            'ip': client_ip,
            'created_at': now,
            'last_access': now
        }
    else:
        # Update last access time
        sessions[session_id]['last_access'] = now

    return sessions[session_id]['data']


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


def get_category_disambiguation_hints(category):
    """Get disambiguation hints based on category type."""
    if not category:
        return []

    category_lower = category.lower()

    # Music-related categories
    if any(term in category_lower for term in ['band', 'rock', 'pop', 'music', 'singer', 'artist', 'rapper', 'hip hop']):
        return ['musician', 'band', 'singer', 'musical artist']

    # Film/TV categories
    if any(term in category_lower for term in ['movie', 'film', 'actor', 'actress', 'star', 'hollywood']):
        return ['actor', 'actress', 'film', 'entertainer']

    # Sports categories
    if any(term in category_lower for term in ['sport', 'athlete', 'player', 'olympic', 'champion', 'football', 'basketball', 'tennis']):
        return ['athlete', 'sportsperson', 'player']

    # Science/academic categories
    if any(term in category_lower for term in ['scientist', 'physicist', 'nobel', 'inventor', 'researcher']):
        return ['scientist', 'physicist', 'researcher']

    # Historical/political categories
    if any(term in category_lower for term in ['leader', 'president', 'monarch', 'king', 'queen', 'politician']):
        return ['politician', 'leader', 'monarch']

    return []


def search_wikipedia_page(item_name, category, headers):
    """Try multiple search strategies to find the best Wikipedia page."""
    api_url = "https://en.wikipedia.org/w/api.php"
    disambiguation_hints = get_category_disambiguation_hints(category)

    # Strategy 1: Try exact title match first
    search_strategies = [
        item_name,  # Exact name
    ]

    # Strategy 2: Try with disambiguation suffixes
    for hint in disambiguation_hints[:2]:  # Limit to first 2 hints
        search_strategies.append(f"{item_name} ({hint})")

    # Strategy 3: Category-enhanced search as fallback
    if category:
        search_strategies.append(f"{item_name} {category}")

    for query in search_strategies:
        search_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': 3  # Get a few results to check relevance
        }

        try:
            resp = requests.get(api_url, params=search_params, headers=headers, timeout=10)
            data = resp.json()

            results = data.get('query', {}).get('search', [])
            if not results:
                continue

            # Check if first result title closely matches our item name
            first_title = results[0]['title'].lower()
            item_lower = item_name.lower()

            # Good match: title starts with or equals the item name
            if first_title.startswith(item_lower) or item_lower in first_title:
                return {
                    'title': results[0]['title'],
                    'search_query': query,
                    'strategy': 'matched'
                }

            # For disambiguation pages, look at other results
            if 'disambiguation' in first_title:
                for result in results[1:]:
                    if item_lower in result['title'].lower():
                        return {
                            'title': result['title'],
                            'search_query': query,
                            'strategy': 'disambiguation_resolved'
                        }
        except requests.RequestException:
            continue

    # Final fallback: just use the first result from original search
    fallback_query = f"{item_name} {category}" if category else item_name
    try:
        resp = requests.get(api_url, params={
            'action': 'query',
            'list': 'search',
            'srsearch': fallback_query,
            'format': 'json',
            'srlimit': 1
        }, headers=headers, timeout=10)
        data = resp.json()
        results = data.get('query', {}).get('search', [])
        if results:
            return {
                'title': results[0]['title'],
                'search_query': fallback_query,
                'strategy': 'fallback'
            }
    except requests.RequestException:
        pass

    return None


def fetch_wikipedia_images(item_name, category=None, max_images=3):
    """
    Fetch images from Wikipedia for the given item, prioritizing the main image.

    Returns a dict with:
        - images: list of image URLs
        - source_page: Wikipedia page title used
        - search_query: the query that found the page
        - status: 'success' | 'no_page_found' | 'no_images' | 'error'
        - error: error message if status is 'error'
    """
    result = {
        'images': [],
        'source_page': None,
        'search_query': None,
        'status': 'no_page_found'
    }

    headers = {'User-Agent': 'PopQuiz/1.0 (https://github.com/bavobbr/top-of-the-pops-agent; bavo.bruylandt@gmail.com)'}
    api_url = "https://en.wikipedia.org/w/api.php"

    try:
        # Step 1: Find the Wikipedia page using improved disambiguation
        page_info = search_wikipedia_page(item_name, category, headers)

        if not page_info:
            return result

        page_title = page_info['title']
        result['source_page'] = page_title
        result['search_query'] = page_info['search_query']

        # Step 2: Get the PRIMARY page image (the main thumbnail/infobox image)
        pageimage_params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'pageimages',
            'piprop': 'original',
            'format': 'json'
        }

        pageimage_resp = requests.get(api_url, params=pageimage_params, headers=headers, timeout=10)
        pageimage_data = pageimage_resp.json()

        for page_id, page_data in pageimage_data.get('query', {}).get('pages', {}).items():
            original = page_data.get('original', {})
            if original.get('source'):
                result['images'].append(original['source'])

        if len(result['images']) >= max_images:
            result['status'] = 'success'
            result['images'] = result['images'][:max_images]
            return result

        # Step 3: Get additional images with improved relevance scoring
        images_params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'images',
            'format': 'json',
            'imlimit': 30
        }

        images_resp = requests.get(api_url, params=images_params, headers=headers, timeout=10)
        images_data = images_resp.json()

        pages = images_data.get('query', {}).get('pages', {})

        # Prepare search terms - include ALL name parts regardless of length (Step 3 fix)
        name_parts = [p.lower() for p in item_name.split()]

        # Patterns for generic/irrelevant images (Step 4: negative scoring)
        generic_patterns = ['map', 'flag', 'chart', 'diagram', 'graph', 'icon',
                           'location', 'coat_of_arms', 'emblem', 'seal']

        # Skip patterns - these are never useful
        skip_patterns = ['commons-logo', 'wiki', 'edit-clear', 'symbol_',
                        'pictogram', 'ambox', 'padlock', 'question',
                        'crystal', 'folder', 'gnome', 'nuvola',
                        'red_pencil', 'disambig', 'stub', 'portal',
                        'p_vip', 'star_full', 'signature', 'autograph',
                        'wma', 'ogg', 'mid', 'octicons', 'oojs']

        # Collect and score images
        scored_images = []

        for page_id, page_data in pages.items():
            for img in page_data.get('images', []):
                img_title = img['title']
                lower_title = img_title.lower()

                # Skip common non-content images
                if any(pattern in lower_title for pattern in skip_patterns):
                    continue

                # Allow jpg, png, gif, and svg (for logos)
                if not any(ext in lower_title for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg']):
                    continue

                # Skip svg icons but allow svg logos
                if '.svg' in lower_title and 'logo' not in lower_title:
                    continue

                # Score based on how many name parts appear in filename
                score = sum(1 for part in name_parts if part in lower_title)

                # Exact match bonus (Step 3 enhancement)
                if item_name.lower() in lower_title:
                    score += 5

                # First word/last word bonus for people (typically first or last name)
                if len(name_parts) >= 2:
                    if name_parts[0] in lower_title:
                        score += 1
                    if name_parts[-1] in lower_title:
                        score += 1

                # Negative scoring for generic images (Step 4)
                if any(pattern in lower_title for pattern in generic_patterns):
                    score -= 3

                scored_images.append((score, img_title))

        # Sort by score (highest first) and get URLs
        scored_images.sort(key=lambda x: -x[0])

        for score, img_title in scored_images:
            if len(result['images']) >= max_images:
                break

            # Get image info with dimensions (Step 4: dimension filtering)
            imageinfo_params = {
                'action': 'query',
                'titles': img_title,
                'prop': 'imageinfo',
                'iiprop': 'url|size',
                'format': 'json'
            }

            info_resp = requests.get(api_url, params=imageinfo_params, headers=headers, timeout=10)
            info_data = info_resp.json()

            for page_id, page_data in info_data.get('query', {}).get('pages', {}).items():
                imageinfo = page_data.get('imageinfo', [])
                if imageinfo:
                    img_info = imageinfo[0]
                    url = img_info.get('url')
                    width = img_info.get('width', 0)
                    height = img_info.get('height', 0)

                    # Skip tiny icons (< 100px) or huge files (> 5000px)
                    if width < 100 or height < 100:
                        continue
                    if width > 5000 or height > 5000:
                        continue

                    if url and url not in result['images']:
                        result['images'].append(url)
                        break

        # Set final status
        if result['images']:
            result['status'] = 'success'
        else:
            result['status'] = 'no_images'

    except requests.RequestException as e:
        result['status'] = 'error'
        result['error'] = f"Network error: {str(e)}"
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"Error fetching Wikipedia images: {e}")

    return result


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


# Cache for suggestions
suggestions_cache = []


@app.route('/api/suggestions')
@limiter.limit("10 per minute")
def get_suggestions():
    """Get AI-generated quiz category suggestions."""
    global suggestions_cache

    # Return cached suggestions if available
    if suggestions_cache:
        return jsonify({'suggestions': suggestions_cache})

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

    try:
        response = model_suggestions.generate_content(prompt)
        result = json.loads(response.text)
        suggestions_cache = result.get('suggestions', [])[:20]
        return jsonify({'suggestions': suggestions_cache})

    except Exception as e:
        # Fallback suggestions if AI fails
        fallback = [
            "movie stars", "rock bands", "car brands", "world leaders",
            "tech billionaires", "80s pop stars", "ancient philosophers",
            "Renaissance painters", "Nobel Prize winners", "Olympic athletes",
            "British monarchs", "90s sitcoms", "video game franchises",
            "fashion designers", "classical composers", "TikTok stars 2020",
            "Marvel superheroes", "world cuisines", "space missions", "dog breeds"
        ]
        return jsonify({'suggestions': fallback})


@app.route('/api/generate-list', methods=['POST'])
@limiter.limit("5 per minute")
@limiter.limit("20 per hour")
def generate_list():
    """Generate a ranked list of items for the given category."""
    data = request.json
    category = data.get('category', '')[:200]  # Max 200 chars
    count = min(max(int(data.get('count', 10)), 1), 100)
    language = data.get('language', 'en')[:5]  # Language code

    if not category:
        return jsonify({'error': 'Category is required'}), 400

    if len(category.strip()) < 2:
        return jsonify({'error': 'Category must be at least 2 characters'}), 400

    language_instruction = get_language_instruction(language)

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

    try:
        response = model_list.generate_content(prompt)
        result = json.loads(response.text)

        # Store in session
        session_data = get_session_data()
        session_data['category'] = category
        session_data['language'] = language
        session_data['items'] = result.get('items', [])
        session_data['properties'] = result.get('properties', [])
        session_data['details_cache'] = {}

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-item-details', methods=['POST'])
@limiter.limit("30 per minute")
def get_item_details():
    """Get details for a specific item including images."""
    data = request.json
    item = data.get('item', '')[:200]  # Max 200 chars
    category = data.get('category', '')[:200]  # Max 200 chars
    properties = data.get('properties', [])[:10]  # Max 10 properties
    language = data.get('language', 'en')[:5]  # Language code

    if not item:
        return jsonify({'error': 'Item is required'}), 400

    # Validate properties are strings and not too long
    properties = [str(p)[:50] for p in properties if isinstance(p, str)]

    session_data = get_session_data()

    # Check cache
    if item in session_data['details_cache']:
        return jsonify(session_data['details_cache'][item])

    # Use session data if not provided
    if not category:
        category = session_data.get('category', 'general')
    if not properties:
        properties = session_data.get('properties', [])
    if language == 'en':
        language = session_data.get('language', 'en')

    properties_str = ', '.join(properties) if properties else 'relevant characteristics'
    language_instruction = get_language_instruction(language)

    prompt = f"""Provide details about "{item}" in the context of {category}.

Return a JSON object with:
- "name": Full/official name
- "description": 2-3 sentence summary
- "properties": Object with values for each of: {properties_str}

IMPORTANT JSON RULES:
1. ALL string values MUST be in double quotes, including dates, years, and descriptions
2. For properties with multiple items (like notable_works, top_songs), use JSON arrays: ["Item 1", "Item 2", "Item 3"]
3. Never use unquoted values - even "9th century" must be "9th century" in quotes

Be concise and factual. Return ONLY valid JSON.{language_instruction}"""

    try:
        response = model_details.generate_content(prompt)

        # Try standard JSON first, fall back to fixup + json5 for malformed responses
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            # Fix unquoted values that contain letters (e.g., "9e eeuw", "circa 1500")
            fixed = response.text
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
            try:
                result = json.loads(fixed)
            except json.JSONDecodeError:
                result = json5.loads(fixed)

        # Render markdown in description and properties
        render_markdown_in_result(result)

        # Fetch Wikipedia images with category context for better disambiguation
        image_result = fetch_wikipedia_images(item, category=category)
        result['images'] = image_result['images']
        result['image_status'] = image_result['status']
        result['image_source'] = image_result.get('source_page')

        # Cache the result
        session_data['details_cache'][item] = result

        return jsonify(result)

    except (json.JSONDecodeError, ValueError) as e:
        # ValueError covers json5 parse errors
        return jsonify({'error': f'Failed to parse AI response: {e}'}), 500
    except Exception as e:
        print(f"Error getting details for '{item}': {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
