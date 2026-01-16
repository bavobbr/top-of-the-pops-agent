import os
import json
import uuid
import re
import requests
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_AI_STUDIO_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# In-memory session storage
sessions = {}


def get_session_data():
    """Get or create session data for current user."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']
    if session_id not in sessions:
        sessions[session_id] = {
            'category': None,
            'items': [],
            'properties': [],
            'details_cache': {}
        }
    return sessions[session_id]


def parse_json_response(text):
    """Extract JSON from Gemini response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if code_block_match:
        text = code_block_match.group(1)

    # Clean up the text
    text = text.strip()

    # Find JSON object or array
    start_idx = text.find('{')
    if start_idx == -1:
        start_idx = text.find('[')
    if start_idx != -1:
        text = text[start_idx:]

    return json.loads(text)


def fetch_wikipedia_images(item_name, category=None, max_images=3):
    """Fetch images from Wikipedia for the given item, prioritizing the main image."""
    images = []
    headers = {'User-Agent': 'PopQuiz/1.0 (Educational Visual Learning App)'}
    search_url = "https://en.wikipedia.org/w/api.php"

    # Build search query with category context for disambiguation
    if category:
        search_query = f"{item_name} {category}"
    else:
        search_query = item_name

    try:
        # Step 1: Search for the Wikipedia page
        search_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': search_query,
            'format': 'json',
            'srlimit': 1
        }

        search_resp = requests.get(search_url, params=search_params, headers=headers, timeout=10)
        search_data = search_resp.json()

        if not search_data.get('query', {}).get('search'):
            return images

        page_title = search_data['query']['search'][0]['title']

        # Step 2: Get the PRIMARY page image (the main thumbnail/infobox image)
        pageimage_params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'pageimages',
            'piprop': 'original',
            'format': 'json'
        }

        pageimage_resp = requests.get(search_url, params=pageimage_params, headers=headers, timeout=10)
        pageimage_data = pageimage_resp.json()

        for page_id, page_data in pageimage_data.get('query', {}).get('pages', {}).items():
            original = page_data.get('original', {})
            if original.get('source'):
                images.append(original['source'])

        if len(images) >= max_images:
            return images[:max_images]

        # Step 3: Get additional images, prioritizing those with the item name
        images_params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'images',
            'format': 'json',
            'imlimit': 30
        }

        images_resp = requests.get(search_url, params=images_params, headers=headers, timeout=10)
        images_data = images_resp.json()

        pages = images_data.get('query', {}).get('pages', {})

        # Prepare search terms from item name for relevance matching
        name_parts = [p.lower() for p in item_name.split() if len(p) > 2]

        # Collect and score images
        scored_images = []

        for page_id, page_data in pages.items():
            for img in page_data.get('images', []):
                img_title = img['title']
                lower_title = img_title.lower()

                # Skip common non-content images (but allow logos for non-person categories)
                skip_patterns = ['commons-logo', 'wiki', 'edit-clear', 'symbol_',
                               'pictogram', 'ambox', 'padlock', 'question',
                               'crystal', 'folder', 'gnome', 'nuvola',
                               'red_pencil', 'disambig', 'stub', 'portal',
                               'p_vip', 'star_full', 'signature', 'autograph',
                               'wma', 'ogg', 'mid', 'octicons', 'oojs']
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
                scored_images.append((score, img_title))

        # Sort by score (highest first) and get URLs
        scored_images.sort(key=lambda x: -x[0])

        for score, img_title in scored_images:
            if len(images) >= max_images:
                break

            imageinfo_params = {
                'action': 'query',
                'titles': img_title,
                'prop': 'imageinfo',
                'iiprop': 'url',
                'format': 'json'
            }

            info_resp = requests.get(search_url, params=imageinfo_params, headers=headers, timeout=10)
            info_data = info_resp.json()

            for page_id, page_data in info_data.get('query', {}).get('pages', {}).items():
                imageinfo = page_data.get('imageinfo', [])
                if imageinfo:
                    url = imageinfo[0].get('url')
                    if url and url not in images:
                        images.append(url)
                        break

    except Exception as e:
        print(f"Error fetching Wikipedia images: {e}")

    return images


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


# Cache for suggestions
suggestions_cache = []


@app.route('/api/suggestions')
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
        response = model.generate_content(prompt)
        result = parse_json_response(response.text)
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
def generate_list():
    """Generate a ranked list of items for the given category."""
    data = request.json
    category = data.get('category', '')
    count = min(max(int(data.get('count', 10)), 1), 100)

    if not category:
        return jsonify({'error': 'Category is required'}), 400

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

Be factual and use commonly accepted rankings. Return ONLY the JSON object, no markdown or other text."""

    try:
        response = model.generate_content(prompt)
        result = parse_json_response(response.text)

        # Store in session
        session_data = get_session_data()
        session_data['category'] = category
        session_data['items'] = result.get('items', [])
        session_data['properties'] = result.get('properties', [])
        session_data['details_cache'] = {}

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-item-details', methods=['POST'])
def get_item_details():
    """Get details for a specific item including images."""
    data = request.json
    item = data.get('item', '')
    category = data.get('category', '')
    properties = data.get('properties', [])

    if not item:
        return jsonify({'error': 'Item is required'}), 400

    session_data = get_session_data()

    # Check cache
    if item in session_data['details_cache']:
        return jsonify(session_data['details_cache'][item])

    # Use session data if not provided
    if not category:
        category = session_data.get('category', 'general')
    if not properties:
        properties = session_data.get('properties', [])

    properties_str = ', '.join(properties) if properties else 'relevant characteristics'

    prompt = f"""Provide details about "{item}" in the context of {category}.

Return a JSON object with:
- "name": Full/official name
- "description": 2-3 sentence summary
- "properties": Object with values for each of: {properties_str}

IMPORTANT: For properties that represent multiple items (like notable_works, top_songs, famous_movies, popular_models, key_achievements, etc.), return them as JSON arrays with 3-5 items, not comma-separated strings.

Example: "notable_works": ["Work 1", "Work 2", "Work 3"]

Be concise and factual. Return ONLY valid JSON, no other text."""

    try:
        response = model.generate_content(prompt)
        result = parse_json_response(response.text)

        # Fetch Wikipedia images with category context for better disambiguation
        images = fetch_wikipedia_images(item, category=category)
        result['images'] = images

        # Cache the result
        session_data['details_cache'][item] = result

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
