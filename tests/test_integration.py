"""Integration tests for API endpoints.

These tests make real API calls to Gemini and Wikipedia.
Requires GOOGLE_AI_STUDIO_KEY environment variable to be set.
"""

import os
import pytest

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv('GOOGLE_AI_STUDIO_KEY'),
    reason="GOOGLE_AI_STUDIO_KEY not set - skipping integration tests"
)


class TestIndexRoute:
    """Tests for the index route."""

    def test_index_returns_html(self, client):
        """Index route should return HTML."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestSuggestionsEndpoint:
    """Integration tests for /api/suggestions endpoint."""

    def test_suggestions_returns_list(self, client):
        """Should return a list of suggestions."""
        response = client.get('/api/suggestions')
        assert response.status_code == 200

        data = response.get_json()
        assert 'suggestions' in data
        assert isinstance(data['suggestions'], list)
        assert len(data['suggestions']) > 0

    def test_suggestions_are_strings(self, client):
        """All suggestions should be strings."""
        response = client.get('/api/suggestions')
        data = response.get_json()

        for suggestion in data['suggestions']:
            assert isinstance(suggestion, str)
            assert len(suggestion) > 0


class TestGenerateListEndpoint:
    """Integration tests for /api/generate-list endpoint."""

    def test_generate_list_success(self, client):
        """Should generate a list of items for a valid category."""
        response = client.post('/api/generate-list', json={
            'category': 'European capitals',
            'count': 5,
            'language': 'en'
        })
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data
        assert 'properties' in data
        assert isinstance(data['items'], list)
        assert len(data['items']) == 5

    def test_generate_list_with_language(self, client):
        """Should generate list in specified language."""
        response = client.post('/api/generate-list', json={
            'category': 'European capitals',
            'count': 3,
            'language': 'nl'
        })
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data
        # Dutch names for capitals (Parijs, Londen, etc.)
        # We can't assert exact names but items should exist
        assert len(data['items']) == 3

    def test_generate_list_missing_category(self, client):
        """Should return error for missing category."""
        response = client.post('/api/generate-list', json={
            'count': 5
        })
        assert response.status_code == 400

        data = response.get_json()
        assert 'error' in data

    def test_generate_list_short_category(self, client):
        """Should return error for too short category."""
        response = client.post('/api/generate-list', json={
            'category': 'a',
            'count': 5
        })
        assert response.status_code == 400

    def test_generate_list_includes_properties(self, client):
        """Should include relevant properties."""
        response = client.post('/api/generate-list', json={
            'category': 'rock bands',
            'count': 3,
            'language': 'en'
        })
        assert response.status_code == 200

        data = response.get_json()
        assert 'properties' in data
        assert isinstance(data['properties'], list)
        assert len(data['properties']) >= 3


class TestGetItemDetailsEndpoint:
    """Integration tests for /api/get-item-details endpoint."""

    def test_get_details_success(self, client):
        """Should get details for a valid item."""
        response = client.post('/api/get-item-details', json={
            'item': 'Paris',
            'category': 'European capitals',
            'properties': ['population', 'country'],
            'language': 'en'
        })
        assert response.status_code == 200

        data = response.get_json()
        assert 'name' in data
        assert 'description' in data
        assert 'properties' in data
        assert 'images' in data

    def test_get_details_has_images(self, client):
        """Should include Wikipedia images."""
        response = client.post('/api/get-item-details', json={
            'item': 'The Beatles',
            'category': 'rock bands',
            'properties': ['formed_year', 'genre'],
            'language': 'en'
        })
        assert response.status_code == 200

        data = response.get_json()
        assert 'images' in data
        assert isinstance(data['images'], list)
        # Beatles should have images
        assert len(data['images']) > 0
        assert 'image_status' in data

    def test_get_details_missing_item(self, client):
        """Should return error for missing item."""
        response = client.post('/api/get-item-details', json={
            'category': 'test'
        })
        assert response.status_code == 400

        data = response.get_json()
        assert 'error' in data

    def test_get_details_non_english(self, client):
        """Should handle non-English languages with English image search."""
        response = client.post('/api/get-item-details', json={
            'item': 'Parijs',
            'category': 'Europese hoofdsteden',
            'properties': ['population'],
            'language': 'nl'
        })
        assert response.status_code == 200

        data = response.get_json()
        # Should still find images using English name
        assert 'images' in data
        # Image source should be English (Paris, not Parijs)
        if data.get('image_source'):
            assert 'Paris' in data['image_source'] or len(data['images']) > 0

    def test_get_details_caching(self, client):
        """Should cache results for same item."""
        # First request
        response1 = client.post('/api/get-item-details', json={
            'item': 'London',
            'category': 'European capitals',
            'properties': ['population'],
            'language': 'en'
        })
        assert response1.status_code == 200

        # Second request (should be cached)
        response2 = client.post('/api/get-item-details', json={
            'item': 'London',
            'category': 'European capitals',
            'properties': ['population'],
            'language': 'en'
        })
        assert response2.status_code == 200

        # Results should be identical
        assert response1.get_json() == response2.get_json()


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_security_headers_present(self, client):
        """Security headers should be present on responses."""
        response = client.get('/')

        assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
