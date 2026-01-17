"""Top of the Pops - AI-powered visual learning application."""

import os
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from services.sessions import get_session_data
from services.gemini import generate_suggestions, generate_item_list, generate_item_details
from services.wikipedia import fetch_wikipedia_images
from services.content import get_language_instruction, render_markdown_in_result

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
        if origin:
            origin_host = urlparse(origin).netloc
            request_host = request.host
            if origin_host != request_host:
                return jsonify({
                    'error': 'forbidden',
                    'message': 'Cross-origin requests are not allowed'
                }), 403


@app.after_request
def set_security_headers(response):
    """Set security headers to prevent cross-origin access."""
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


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

    if suggestions_cache:
        return jsonify({'suggestions': suggestions_cache})

    try:
        result = generate_suggestions()
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
    category = data.get('category', '')[:200]
    count = min(max(int(data.get('count', 10)), 1), 100)
    language = data.get('language', 'en')[:5]

    if not category:
        return jsonify({'error': 'Category is required'}), 400

    if len(category.strip()) < 2:
        return jsonify({'error': 'Category must be at least 2 characters'}), 400

    language_instruction = get_language_instruction(language)

    try:
        result = generate_item_list(category, count, language_instruction)

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
    item = data.get('item', '')[:200]
    category = data.get('category', '')[:200]
    properties = data.get('properties', [])[:10]
    language = data.get('language', 'en')[:5]

    if not item:
        return jsonify({'error': 'Item is required'}), 400

    # Validate properties
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

    language_instruction = get_language_instruction(language)

    try:
        result = generate_item_details(item, category, properties, language, language_instruction)

        # Render markdown in description and properties
        render_markdown_in_result(result)

        # Fetch Wikipedia images using English names for better results
        search_name = result.pop('english_name', None) or item
        search_category = result.pop('english_category', None) or category
        image_result = fetch_wikipedia_images(search_name, category=search_category)
        result['images'] = image_result['images']
        result['image_status'] = image_result['status']
        result['image_source'] = image_result.get('source_page')

        # Cache the result
        session_data['details_cache'][item] = result

        return jsonify(result)

    except (ValueError, Exception) as e:
        print(f"Error getting details for '{item}': {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
