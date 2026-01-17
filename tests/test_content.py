"""Unit tests for services/content.py."""

import pytest
from services.content import (
    render_markdown,
    render_markdown_in_result,
    get_language_instruction,
    SUPPORTED_LANGUAGES
)


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_basic_text(self):
        """Plain text should be wrapped in <p> tags."""
        result = render_markdown("Hello world")
        assert result == "<p>Hello world</p>"

    def test_bold_text(self):
        """Bold markdown should render as <strong>."""
        result = render_markdown("This is **bold** text")
        assert "<strong>bold</strong>" in result

    def test_italic_text(self):
        """Italic markdown should render as <em>."""
        result = render_markdown("This is *italic* text")
        assert "<em>italic</em>" in result

    def test_inline_mode(self):
        """Inline mode should strip wrapping <p> tags."""
        result = render_markdown("Hello world", inline=True)
        assert result == "Hello world"

    def test_inline_mode_with_formatting(self):
        """Inline mode should preserve inner formatting."""
        result = render_markdown("**bold** text", inline=True)
        assert result == "<strong>bold</strong> text"

    def test_unordered_list(self):
        """Unordered lists should render properly."""
        result = render_markdown("- Item 1\n- Item 2")
        assert "<ul>" in result
        assert "<li>" in result

    def test_ordered_list(self):
        """Ordered lists should render properly."""
        result = render_markdown("1. First\n2. Second")
        assert "<ol>" in result
        assert "<li>" in result

    def test_empty_input(self):
        """Empty string should return empty string."""
        assert render_markdown("") == ""
        assert render_markdown(None) == ""

    def test_script_tag_stripped(self):
        """Script tags should be stripped for security."""
        result = render_markdown("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_dangerous_attributes_stripped(self):
        """Dangerous attributes should be stripped."""
        result = render_markdown('<a href="javascript:alert()">link</a>')
        assert "javascript:" not in result


class TestRenderMarkdownInResult:
    """Tests for render_markdown_in_result function."""

    def test_renders_description(self):
        """Should render markdown in description field."""
        result = {'description': 'This is **bold**'}
        render_markdown_in_result(result)
        assert "<strong>bold</strong>" in result['description']

    def test_renders_string_properties(self):
        """Should render markdown in string property values."""
        result = {
            'properties': {
                'bio': 'Born in **1990**'
            }
        }
        render_markdown_in_result(result)
        assert "<strong>1990</strong>" in result['properties']['bio']

    def test_renders_list_properties(self):
        """Should render markdown in list property values."""
        result = {
            'properties': {
                'albums': ['**Album 1**', '*Album 2*']
            }
        }
        render_markdown_in_result(result)
        assert "<strong>Album 1</strong>" in result['properties']['albums'][0]
        assert "<em>Album 2</em>" in result['properties']['albums'][1]

    def test_preserves_non_string_properties(self):
        """Should not modify non-string property values."""
        result = {
            'properties': {
                'count': 42,
                'active': True
            }
        }
        render_markdown_in_result(result)
        assert result['properties']['count'] == 42
        assert result['properties']['active'] is True

    def test_handles_missing_fields(self):
        """Should handle results without description or properties."""
        result = {'name': 'Test'}
        render_markdown_in_result(result)
        assert result == {'name': 'Test'}


class TestGetLanguageInstruction:
    """Tests for get_language_instruction function."""

    def test_english_returns_empty(self):
        """English should return empty instruction."""
        assert get_language_instruction('en') == ''

    def test_supported_language_returns_instruction(self):
        """Supported languages should return proper instruction."""
        result = get_language_instruction('nl')
        assert 'Dutch' in result
        assert 'IMPORTANT' in result

    def test_unsupported_language_returns_empty(self):
        """Unsupported language codes should return empty string."""
        assert get_language_instruction('xx') == ''

    def test_all_supported_languages(self):
        """All supported languages should return non-empty instructions."""
        for code in SUPPORTED_LANGUAGES:
            if code != 'en':
                result = get_language_instruction(code)
                assert result != '', f"Language {code} should return instruction"
                assert SUPPORTED_LANGUAGES[code] in result


class TestSupportedLanguages:
    """Tests for SUPPORTED_LANGUAGES constant."""

    def test_contains_common_languages(self):
        """Should contain commonly used languages."""
        assert 'en' in SUPPORTED_LANGUAGES
        assert 'es' in SUPPORTED_LANGUAGES
        assert 'fr' in SUPPORTED_LANGUAGES
        assert 'de' in SUPPORTED_LANGUAGES
        assert 'ja' in SUPPORTED_LANGUAGES
        assert 'zh' in SUPPORTED_LANGUAGES

    def test_has_20_languages(self):
        """Should have exactly 20 languages."""
        assert len(SUPPORTED_LANGUAGES) == 20
