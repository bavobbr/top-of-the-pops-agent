"""Unit tests for services/wikipedia.py."""

import pytest
import responses
from services.wikipedia import (
    get_category_disambiguation_hints,
    search_wikipedia_page,
    fetch_wikipedia_images,
    API_URL,
    USER_AGENT
)


class TestGetCategoryDisambiguationHints:
    """Tests for get_category_disambiguation_hints function."""

    def test_music_categories(self):
        """Should return music hints for music-related categories."""
        hints = get_category_disambiguation_hints("80s rock bands")
        assert "musician" in hints or "band" in hints

        hints = get_category_disambiguation_hints("pop singers")
        assert "singer" in hints or "musician" in hints

        hints = get_category_disambiguation_hints("hip hop artists")
        assert "musician" in hints or "musical artist" in hints

    def test_film_categories(self):
        """Should return film hints for film-related categories."""
        hints = get_category_disambiguation_hints("movie stars")
        assert "actor" in hints or "actress" in hints

        hints = get_category_disambiguation_hints("Hollywood actors")
        assert "actor" in hints

    def test_sports_categories(self):
        """Should return sports hints for sports-related categories."""
        hints = get_category_disambiguation_hints("Olympic athletes")
        assert "athlete" in hints or "sportsperson" in hints

        hints = get_category_disambiguation_hints("football players")
        assert "player" in hints or "athlete" in hints

    def test_science_categories(self):
        """Should return science hints for science-related categories."""
        hints = get_category_disambiguation_hints("Nobel Prize scientists")
        assert "scientist" in hints

        hints = get_category_disambiguation_hints("famous physicists")
        assert "physicist" in hints or "scientist" in hints

    def test_political_categories(self):
        """Should return political hints for political categories."""
        hints = get_category_disambiguation_hints("world leaders")
        assert "leader" in hints or "politician" in hints

        hints = get_category_disambiguation_hints("British monarchs")
        assert "monarch" in hints

    def test_generic_category(self):
        """Should return empty list for generic categories."""
        hints = get_category_disambiguation_hints("car brands")
        assert hints == []

        hints = get_category_disambiguation_hints("dog breeds")
        assert hints == []

    def test_empty_category(self):
        """Should return empty list for empty category."""
        assert get_category_disambiguation_hints("") == []
        assert get_category_disambiguation_hints(None) == []

    def test_case_insensitive(self):
        """Should be case insensitive."""
        hints_lower = get_category_disambiguation_hints("rock bands")
        hints_upper = get_category_disambiguation_hints("ROCK BANDS")
        hints_mixed = get_category_disambiguation_hints("Rock Bands")
        assert hints_lower == hints_upper == hints_mixed


class TestSearchWikipediaPage:
    """Tests for search_wikipedia_page function with mocked responses."""

    @responses.activate
    def test_exact_match_found(self):
        """Should find page with exact match."""
        responses.add(
            responses.GET,
            API_URL,
            json={
                "query": {
                    "search": [{"title": "The Beatles"}]
                }
            },
            status=200
        )

        headers = {"User-Agent": USER_AGENT}
        result = search_wikipedia_page("The Beatles", "rock bands", headers)

        assert result is not None
        assert result["title"] == "The Beatles"

    @responses.activate
    def test_no_results(self):
        """Should return None when no results found."""
        # Mock multiple search attempts with no results
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )

        headers = {"User-Agent": USER_AGENT}
        result = search_wikipedia_page("xyznonexistent123", "", headers)

        assert result is None

    @responses.activate
    def test_disambiguation_resolution(self):
        """Should resolve disambiguation pages by finding item name in other results."""
        # First search returns disambiguation page, second result contains the name
        responses.add(
            responses.GET, API_URL,
            json={
                "query": {
                    "search": [
                        {"title": "Prince (disambiguation)"},
                        {"title": "Prince (musician)"}
                    ]
                }
            },
            status=200
        )

        headers = {"User-Agent": USER_AGENT}
        result = search_wikipedia_page("Prince", "80s musicians", headers)

        assert result is not None
        # Should find the musician since "prince" is in the title
        assert "Prince" in result["title"]


class TestFetchWikipediaImages:
    """Tests for fetch_wikipedia_images function."""

    @responses.activate
    def test_returns_result_structure(self):
        """Should return proper result structure even on failure."""
        # No mocked responses - will fail to find page
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": []}},
            status=200
        )

        result = fetch_wikipedia_images("nonexistent_item_xyz")

        assert "images" in result
        assert "source_page" in result
        assert "status" in result
        assert isinstance(result["images"], list)

    @responses.activate
    def test_successful_image_fetch(self):
        """Should fetch images successfully."""
        # Mock search
        responses.add(
            responses.GET, API_URL,
            json={"query": {"search": [{"title": "Test Page"}]}},
            status=200
        )
        # Mock pageimages
        responses.add(
            responses.GET, API_URL,
            json={
                "query": {
                    "pages": {
                        "123": {
                            "original": {"source": "https://example.com/image.jpg"}
                        }
                    }
                }
            },
            status=200
        )
        # Mock images list
        responses.add(
            responses.GET, API_URL,
            json={"query": {"pages": {"123": {"images": []}}}},
            status=200
        )

        result = fetch_wikipedia_images("Test", category="test category")

        assert result["status"] == "success"
        assert len(result["images"]) >= 1
        assert result["source_page"] == "Test Page"

    def test_max_images_parameter(self):
        """Should respect max_images parameter."""
        # This is a simple parameter check - actual behavior tested in integration
        # Just verify the function accepts the parameter
        result = fetch_wikipedia_images("test", max_images=1)
        assert len(result["images"]) <= 1


class TestUserAgent:
    """Tests for user agent configuration."""

    def test_user_agent_format(self):
        """User agent should contain required information."""
        assert "PopQuiz" in USER_AGENT
        assert "@" in USER_AGENT  # Should have email
        assert "github" in USER_AGENT.lower() or "http" in USER_AGENT.lower()
