# AI Agent Guidelines

This document helps AI coding agents (Claude, Codex, Gemini, etc.) understand the project structure, coding conventions, and how to work effectively with this codebase.

## Project Overview

**Top of the Pops** is a Flask-based visual learning app that generates quizzes using Google's Gemini AI and fetches images from Wikipedia. It's a monolithic single-page application with server-side session management.

## Architecture

```
popquiz/
├── app.py              # All backend logic (Flask routes, AI calls, Wikipedia API)
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Single-page frontend (Alpine.js + Tailwind CSS)
├── static/
│   ├── app.js          # Alpine.js component logic
│   ├── favicon.svg     # App icon
│   └── og-image.svg    # Social sharing image
├── Dockerfile          # Cloud Run deployment
└── .env                # Environment variables (not committed)
```

## Coding Style

### Python (app.py)

- **Framework**: Flask 3.x with function-based views
- **Formatting**: 4-space indentation, ~100 char line length
- **Imports**: Standard library first, then third-party, then local
- **Error handling**: Try/except with specific exception types, return JSON errors with appropriate HTTP codes
- **Comments**: Minimal, code should be self-documenting; use comments for "why" not "what"

```python
# Good: Explains why
# Fix unquoted values that contain letters (e.g., "9e eeuw", "circa 1500")
fixed = re.sub(pattern, replacement, text)

# Bad: Explains what (obvious from code)
# Apply regex substitution
fixed = re.sub(pattern, replacement, text)
```

### JavaScript (static/app.js)

- **Framework**: Alpine.js 3.x (reactive, declarative)
- **Pattern**: Single Alpine component returned by `popquiz()` function
- **State**: All state in the component object, no external stores
- **Async**: Use async/await for API calls
- **Error handling**: Try/catch with user-friendly error messages

### HTML (templates/index.html)

- **Templating**: Jinja2 (minimal usage, mostly static)
- **Styling**: Tailwind CSS via CDN, inline classes
- **Reactivity**: Alpine.js directives (x-data, x-show, x-for, @click, etc.)
- **No build step**: All dependencies loaded via CDN

## Key Patterns

### API Response Format

All API endpoints return JSON:
```python
# Success
return jsonify({'key': 'value'}), 200

# Error
return jsonify({'error': 'message'}), 400  # or 429, 500
```

### Session Management

Server-side sessions with in-memory storage:
```python
session_data = get_session_data()  # Returns dict for current session
session_data['key'] = value        # Automatically persisted
```

### Gemini AI Calls

Three separate model instances with different configs:
- `model_suggestions`: JSON schema for suggestions
- `model_list`: JSON schema for item lists
- `model_details`: JSON mode only (dynamic properties)

```python
response = model.generate_content(prompt)
result = json.loads(response.text)  # May need json5 fallback
```

### Wikipedia API

Always include User-Agent header:
```python
headers = {
    'User-Agent': 'TopOfThePops/1.0 (https://github.com/user/repo; email@example.com)'
}
response = requests.get(url, params=params, headers=headers, timeout=10)
```

## Testing

### Manual Testing

No automated test suite currently. Test manually:

```bash
# Start the app
python app.py

# Test suggestions endpoint
curl http://localhost:5000/api/suggestions

# Test list generation
curl -X POST http://localhost:5000/api/generate-list \
  -H "Content-Type: application/json" \
  -d '{"category": "European capitals", "count": 10, "language": "en"}'

# Test item details
curl -X POST http://localhost:5000/api/get-item-details \
  -H "Content-Type: application/json" \
  -d '{"item": "Paris", "category": "European capitals", "properties": ["population"], "language": "en"}'
```

### Key Test Cases

1. **JSON parsing**: Test with non-English languages that may produce unquoted values
2. **Image search**: Test disambiguation (e.g., "Prince" with music category)
3. **Rate limiting**: Endpoints have per-minute/hour limits
4. **Input validation**: Category/item names are length-limited

## Common Tasks

### Adding a New API Endpoint

1. Add route in `app.py`:
```python
@app.route('/api/new-endpoint', methods=['POST'])
@limiter.limit("10 per minute")
def new_endpoint():
    data = request.json
    # Validate input
    # Process
    return jsonify(result)
```

2. Add frontend call in `static/app.js`:
```javascript
async newMethod() {
    const response = await fetch('/api/new-endpoint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: value })
    });
    const data = await response.json();
    // Handle response
}
```

### Modifying Gemini Prompts

Prompts are inline strings in `app.py`. Key considerations:
- Request JSON output explicitly
- For non-English: request `english_name` and `english_category` for image search
- Include JSON formatting rules to avoid parse errors

### Adding Dependencies

1. Add to `requirements.txt` with pinned version
2. Update Dockerfile if needed (usually not)
3. Import in `app.py`

## Environment Variables

Required in `.env`:
```
GOOGLE_AI_STUDIO_KEY=your_api_key
```

## Deployment

```bash
# Local Docker
docker build -t popquiz .
docker run -p 8080:8080 -e GOOGLE_AI_STUDIO_KEY=key popquiz

# Google Cloud Run
gcloud run deploy popquiz --source . --allow-unauthenticated
```

## Known Limitations

1. **No database**: Sessions stored in memory, lost on restart
2. **No auth**: Public API, protected only by rate limiting
3. **No tests**: Manual testing only
4. **Single file backend**: All logic in app.py (~770 lines)

## Security Considerations

- Rate limiting on all API endpoints
- CORS protection (same-origin only)
- HTML sanitization for AI-generated markdown
- Input length limits on all user inputs
- No user data persistence (session-only)
