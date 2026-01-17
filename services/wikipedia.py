"""Wikipedia API integration for fetching images."""

import requests

# User agent for Wikipedia API requests
USER_AGENT = 'PopQuiz/1.0 (https://github.com/bavobbr/top-of-the-pops-agent; bavo.bruylandt@gmail.com)'
API_URL = "https://en.wikipedia.org/w/api.php"


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
            resp = requests.get(API_URL, params=search_params, headers=headers, timeout=10)
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
        resp = requests.get(API_URL, params={
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

    headers = {'User-Agent': USER_AGENT}

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

        pageimage_resp = requests.get(API_URL, params=pageimage_params, headers=headers, timeout=10)
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

        images_resp = requests.get(API_URL, params=images_params, headers=headers, timeout=10)
        images_data = images_resp.json()

        pages = images_data.get('query', {}).get('pages', {})

        # Prepare search terms - include ALL name parts regardless of length
        name_parts = [p.lower() for p in item_name.split()]

        # Patterns for generic/irrelevant images (negative scoring)
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

                # Exact match bonus
                if item_name.lower() in lower_title:
                    score += 5

                # First word/last word bonus for people (typically first or last name)
                if len(name_parts) >= 2:
                    if name_parts[0] in lower_title:
                        score += 1
                    if name_parts[-1] in lower_title:
                        score += 1

                # Negative scoring for generic images
                if any(pattern in lower_title for pattern in generic_patterns):
                    score -= 3

                scored_images.append((score, img_title))

        # Sort by score (highest first) and get URLs
        scored_images.sort(key=lambda x: -x[0])

        for score, img_title in scored_images:
            if len(result['images']) >= max_images:
                break

            # Get image info with dimensions
            imageinfo_params = {
                'action': 'query',
                'titles': img_title,
                'prop': 'imageinfo',
                'iiprop': 'url|size',
                'format': 'json'
            }

            info_resp = requests.get(API_URL, params=imageinfo_params, headers=headers, timeout=10)
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
