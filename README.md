# Top of the Pops

An AI-powered visual learning application that helps users study ranked lists across various categories using generative AI and Wikipedia imagery.

## Features

- **Dynamic Quiz Generation**: Select any category (movie stars, car brands, Nobel Prize winners, etc.) and specify how many items to study (5-50)
- **AI-Generated Content**: Uses Google's Gemini 2.0 Flash model to create ranked lists with contextually relevant properties
- **Visual Flashcards**: Displays items with up to 3 images fetched from Wikipedia, descriptions, and structured facts
- **Interactive Navigation**: Browse items sequentially, randomly, or via an item list modal
- **Smart Image Selection**: Intelligent Wikipedia image fetching with category-aware disambiguation
- **Session Caching**: Caches item details per session for performance
- **AI Category Suggestions**: Provides 20 diverse category ideas on the home screen

## Tech Stack

### Backend
- **Framework**: Flask 3.0.0
- **AI**: Google Generative AI (Gemini 2.0 Flash)
- **External APIs**: Wikipedia API
- **Runtime**: Python 3.11

### Frontend
- **Styling**: Tailwind CSS (CDN)
- **Reactivity**: Alpine.js 3.x
- **Fonts**: Righteous (display), Space Mono (monospace)
- **Design**: Retro 80s/90s aesthetic

### Deployment
- **Containerization**: Docker (python:3.11-slim)
- **Server**: Gunicorn
- **Platform**: Google Cloud Run

## Architecture

```
popquiz/
├── app.py                  # Flask backend with AI and Wikipedia integration
├── requirements.txt        # Python dependencies
├── .env                    # Environment config (GOOGLE_AI_STUDIO_KEY)
├── Dockerfile              # Cloud Run deployment config
├── templates/
│   └── index.html          # Single-page application
└── static/
    └── app.js              # Alpine.js frontend logic
```

**Pattern**: Monolithic Flask app with a single-page frontend. Session state stored server-side with unique session IDs.

### Data Flow

```
User Input (Category)
       ↓
/api/generate-list → Gemini AI (ranked items + properties)
       ↓
Session Storage (server-side)
       ↓
/api/get-item-details → Gemini AI (details) + Wikipedia (images)
       ↓
Response Cache (per session)
       ↓
Frontend Renders (Alpine.js)
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve main HTML |
| GET | `/api/suggestions` | Get 20 category suggestions |
| POST | `/api/generate-list` | Generate ranked item list for category |
| POST | `/api/get-item-details` | Get details + images for specific item |

## Setup

### Prerequisites
- Python 3.11+
- Google AI Studio API key

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd popquiz
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file with your API key:
   ```
   GOOGLE_AI_STUDIO_KEY=your_api_key_here
   ```

5. Run the application:
   ```bash
   python app.py
   ```

   The app will be available at `http://localhost:5000`

## Docker Deployment

Build and run locally:
```bash
docker build -t popquiz .
docker run -p 8080:8080 -e GOOGLE_AI_STUDIO_KEY=your_key popquiz
```

Deploy to Google Cloud Run:
```bash
gcloud run deploy popquiz --source . --allow-unauthenticated
```

## Usage

1. Enter a category (e.g., "greatest rock bands of all time") or select from AI suggestions
2. Adjust the slider to choose how many items (5-50)
3. Click "Generate Quiz" to create the study set
4. Browse through items using Next/Random buttons or the item list
5. View images, descriptions, and properties for each item
6. Start a new quiz anytime with the "New Quiz" button

## License

MIT
