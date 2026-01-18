# AI Agent Guidelines

This document helps AI coding agents (Claude, Codex, Gemini, etc.) understand the project structure, coding conventions, and how to work effectively with this codebase.

## Project Overview

**Top of the Pops** is a Flask-based visual learning app that generates quizzes using Google's Gemini AI and fetches images from Wikipedia. It's a monolithic single-page application with server-side session management.

## Architecture

```
popquiz/
├── app.py              # Flask routes and app setup (~190 lines)
├── services/           # Backend service modules
│   ├── __init__.py
│   ├── sessions.py     # Session management (~70 lines)
│   ├── gemini.py       # Gemini AI integration (~130 lines)
│   ├── wikipedia.py    # Wikipedia image fetching (~230 lines)
│   └── content.py      # Markdown rendering, language support (~70 lines)
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

### Service Modules

- **services/sessions.py**: In-memory session storage, cleanup, per-IP limits
- **services/gemini.py**: AI model configuration, prompt generation, JSON parsing
- **services/wikipedia.py**: Page search, disambiguation, image fetching and scoring
- **services/content.py**: Markdown→HTML conversion, language instructions

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

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov=app --cov-report=term-missing

# Run only unit tests (no API key needed)
pytest tests/test_content.py tests/test_gemini.py tests/test_wikipedia.py

# Run integration tests (requires GOOGLE_AI_STUDIO_KEY)
pytest tests/test_integration.py
```

### Test Structure

```
tests/
├── conftest.py           # Pytest fixtures (Flask test client)
├── test_content.py       # Unit tests for markdown/language (21 tests)
├── test_gemini.py        # Unit tests for JSON parsing (17 tests)
├── test_wikipedia.py     # Unit tests for Wikipedia helpers (15 tests)
└── test_integration.py   # Integration tests for API endpoints (14 tests)
```

### Test Categories

1. **Unit tests** (no external dependencies):
   - `test_content.py`: Markdown rendering, HTML sanitization, language instructions
   - `test_gemini.py`: JSON parsing, unquoted value fixing, edge cases
   - `test_wikipedia.py`: Disambiguation hints, mocked API responses

2. **Integration tests** (require API key):
   - `test_integration.py`: Full API endpoint tests with real Gemini and Wikipedia calls
   - Skipped automatically if `GOOGLE_AI_STUDIO_KEY` not set

### Adding New Tests

When adding features, add corresponding tests:
- Unit tests for pure functions in `services/`
- Integration tests for API endpoint behavior
- Use `responses` library to mock HTTP calls in unit tests

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

**Important for AI Agents**: Do NOT deploy automatically. Deployments interrupt the live service and should be triggered by the user. Instead:
1. Commit and push your changes
2. Inform the user that changes are ready to deploy
3. Let the user run the deployment command themselves

```bash
# Local development
python app.py

# Local Docker
docker build -t popquiz .
docker run -p 8080:8080 -e GOOGLE_AI_STUDIO_KEY=key popquiz

# Google Cloud Run (run by user, not by AI agents)
gcloud run deploy popquiz --source . --allow-unauthenticated --region us-central1
```

**Live URL**: https://popquiz-655271433629.us-central1.run.app

## Known Limitations

1. **No database**: Sessions stored in memory, lost on restart
2. **No auth**: Public API, protected only by rate limiting

## Security Considerations

- Rate limiting on all API endpoints
- CORS protection (same-origin only)
- HTML sanitization for AI-generated markdown
- Input length limits on all user inputs
- No user data persistence (session-only)
