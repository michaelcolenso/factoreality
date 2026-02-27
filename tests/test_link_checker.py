"""Tests for utils/link_checker.py

Network calls are mocked — these tests validate extraction and result
classification logic, not actual HTTP connectivity.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

from utils.link_checker import extract_urls, check_url, check_file


class TestExtractUrls:
    def test_extracts_markdown_link(self):
        text = "See [the docs](https://example.com/docs) for info."
        urls = extract_urls(text)
        assert "https://example.com/docs" in urls

    def test_extracts_bare_url(self):
        text = "Visit https://example.com for more."
        assert "https://example.com" in extract_urls(text)

    def test_extracts_http_and_https(self):
        text = "http://a.com and https://b.com"
        urls = extract_urls(text)
        assert "http://a.com" in urls
        assert "https://b.com" in urls

    def test_deduplicates(self):
        text = "https://example.com and https://example.com again."
        urls = extract_urls(text)
        assert urls.count("https://example.com") == 1

    def test_no_urls_returns_empty(self):
        assert extract_urls("No links here at all.") == []

    def test_multiple_urls_all_extracted(self):
        text = (
            "[Source 1](https://a.com) and [Source 2](https://b.com) "
            "and [Source 3](https://c.com)"
        )
        urls = extract_urls(text)
        assert len(urls) == 3

    def test_strips_trailing_punctuation_from_bare_url(self):
        # Parenthesis in URL pattern ends before ) by design
        urls = extract_urls("See https://example.com.")
        # Trailing period should not be part of URL
        assert all(not u.endswith(".") for u in urls)


class TestCheckUrl:
    def test_returns_200_for_ok_response(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            url, status = check_url("https://example.com")
        assert url == "https://example.com"
        assert status == 200

    def test_returns_404_for_http_error(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://example.com/missing",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ):
            url, status = check_url("https://example.com/missing")
        assert status == 404

    def test_returns_error_string_for_connection_error(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=ConnectionError("connection refused"),
        ):
            url, status = check_url("https://unreachable.example")
        assert isinstance(status, str)

    def test_returns_url_unchanged(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        original = "https://example.com/path?q=1"
        with patch("urllib.request.urlopen", return_value=mock_response):
            url, _ = check_url(original)
        assert url == original


class TestCheckFile:
    def test_missing_file_returns_summary_with_not_found(self, tmp_path):
        result = check_file(tmp_path / "missing.md")
        assert "not found" in result["summary"]

    def test_file_with_no_urls_returns_empty_lists(self, tmp_path):
        f = tmp_path / "no_links.md"
        f.write_text("No links in this file.", encoding="utf-8")
        result = check_file(f)
        assert result["ok"] == []
        assert result["broken"] == []

    def test_all_ok_urls_classified_correctly(self, tmp_path):
        f = tmp_path / "links.md"
        f.write_text(
            "See [docs](https://example.com/a) and [more](https://example.com/b).",
            encoding="utf-8",
        )
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = check_file(f)

        assert len(result["ok"]) == 2
        assert result["broken"] == []

    def test_broken_url_classified_correctly(self, tmp_path):
        f = tmp_path / "links.md"
        f.write_text("See [missing](https://example.com/gone).", encoding="utf-8")

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://example.com/gone",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ):
            result = check_file(f)

        assert len(result["broken"]) == 1
        assert result["ok"] == []

    def test_summary_string_present(self, tmp_path):
        f = tmp_path / "links.md"
        f.write_text("No links.", encoding="utf-8")
        result = check_file(f)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0
