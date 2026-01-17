"""Unit tests for services/gemini.py."""

import pytest
from services.gemini import parse_json_response


class TestParseJsonResponse:
    """Tests for parse_json_response function."""

    def test_valid_json(self):
        """Should parse valid JSON correctly."""
        text = '{"name": "Test", "value": 42}'
        result = parse_json_response(text)
        assert result == {"name": "Test", "value": 42}

    def test_valid_json_with_array(self):
        """Should parse JSON with arrays."""
        text = '{"items": ["a", "b", "c"]}'
        result = parse_json_response(text)
        assert result == {"items": ["a", "b", "c"]}

    def test_unquoted_string_value(self):
        """Should fix unquoted string values like '9e eeuw'."""
        text = '{"founded_year": 9e eeuw, "name": "Test"}'
        result = parse_json_response(text)
        assert result["founded_year"] == "9e eeuw"
        assert result["name"] == "Test"

    def test_unquoted_value_with_numbers(self):
        """Should fix unquoted values that contain numbers and text."""
        text = '{"population": 3.2 million}'
        result = parse_json_response(text)
        assert result["population"] == "3.2 million"

    def test_unquoted_value_at_end(self):
        """Should fix unquoted values at end of object."""
        text = '''{
            "name": "Madrid",
            "founded": 9th century
        }'''
        result = parse_json_response(text)
        assert result["founded"] == "9th century"

    def test_mixed_quoted_and_unquoted(self):
        """Should handle mix of quoted and unquoted values."""
        text = '''{
            "name": "Paris",
            "founded": circa 250 BC,
            "country": "France"
        }'''
        result = parse_json_response(text)
        assert result["name"] == "Paris"
        assert result["founded"] == "circa 250 BC"
        assert result["country"] == "France"

    def test_nested_objects(self):
        """Should handle nested objects."""
        text = '{"outer": {"inner": "value"}}'
        result = parse_json_response(text)
        assert result == {"outer": {"inner": "value"}}

    def test_boolean_values(self):
        """Should preserve boolean values."""
        text = '{"active": true, "deleted": false}'
        result = parse_json_response(text)
        assert result["active"] is True
        assert result["deleted"] is False

    def test_null_values(self):
        """Should preserve null values."""
        text = '{"value": null}'
        result = parse_json_response(text)
        assert result["value"] is None

    def test_numeric_values(self):
        """Should preserve numeric values."""
        text = '{"integer": 42, "float": 3.14}'
        result = parse_json_response(text)
        assert result["integer"] == 42
        assert result["float"] == 3.14

    def test_array_response(self):
        """Should parse array responses."""
        text = '["item1", "item2", "item3"]'
        result = parse_json_response(text)
        assert result == ["item1", "item2", "item3"]

    def test_unicode_content(self):
        """Should handle unicode characters."""
        text = '{"city": "東京", "country": "日本"}'
        result = parse_json_response(text)
        assert result["city"] == "東京"
        assert result["country"] == "日本"

    def test_special_characters_in_strings(self):
        """Should handle special characters in quoted strings."""
        text = '{"text": "Hello, \\"world\\"!"}'
        result = parse_json_response(text)
        assert result["text"] == 'Hello, "world"!'

    def test_empty_object(self):
        """Should parse empty object."""
        text = '{}'
        result = parse_json_response(text)
        assert result == {}

    def test_empty_array(self):
        """Should parse empty array."""
        text = '[]'
        result = parse_json_response(text)
        assert result == []

    def test_whitespace_handling(self):
        """Should handle various whitespace."""
        text = '''
        {
            "name"  :  "Test"  ,
            "value" :  42
        }
        '''
        result = parse_json_response(text)
        assert result["name"] == "Test"
        assert result["value"] == 42

    def test_invalid_json_raises(self):
        """Should raise error for completely invalid JSON."""
        text = 'not json at all'
        with pytest.raises((ValueError, Exception)):
            parse_json_response(text)
