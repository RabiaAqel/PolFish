"""Tests for polymarket_predictor.parser.prediction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from polymarket_predictor.parser.prediction import Prediction, PredictionParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser():
    return PredictionParser(llm_api_key="", llm_model="gpt-4o-mini")


@pytest.fixture
def parser_with_key():
    return PredictionParser(llm_api_key="sk-test-key", llm_model="gpt-4o-mini")


# ---------------------------------------------------------------------------
# Regex extraction -- probability patterns
# ---------------------------------------------------------------------------


class TestExtractProbability:
    def test_percent_probability(self, parser):
        assert parser._extract_probability("65% probability of success") == 0.65

    def test_probability_of_percent(self, parser):
        assert parser._extract_probability("probability of 65%") == 0.65

    def test_yes_colon_percent(self, parser):
        assert parser._extract_probability("Yes: 65%") == 0.65

    def test_approximately_percent(self, parser):
        assert parser._extract_probability("approximately 65%") == 0.65

    def test_estimated_at_percent(self, parser):
        assert parser._extract_probability("estimated at 65%") == 0.65

    def test_yes_outcome_percent(self, parser):
        assert parser._extract_probability("Yes outcome: 65%") == 0.65

    def test_100_percent(self, parser):
        assert parser._extract_probability("100% probability") == 1.0

    def test_0_percent(self, parser):
        assert parser._extract_probability("0% probability") == 0.0

    def test_no_match(self, parser):
        assert parser._extract_probability("no probability here") is None

    def test_decimal_probability(self, parser):
        assert parser._extract_probability("72.5% probability") == 0.725


# ---------------------------------------------------------------------------
# Regex extraction -- confidence
# ---------------------------------------------------------------------------


class TestExtractConfidence:
    def test_high_confidence(self, parser):
        assert parser._extract_confidence("We have high confidence in this") == "high"

    def test_strong_consensus(self, parser):
        assert parser._extract_confidence("There is strong consensus among agents") == "high"

    def test_uncertain(self, parser):
        assert parser._extract_confidence("The outcome is uncertain") == "low"

    def test_moderate_confidence(self, parser):
        assert parser._extract_confidence("moderate confidence in the prediction") == "medium"

    def test_no_keywords_default_medium(self, parser):
        assert parser._extract_confidence("A plain report with no signal words") == "medium"

    def test_very_likely(self, parser):
        assert parser._extract_confidence("It is very likely to happen") == "high"

    def test_divided_opinions(self, parser):
        assert parser._extract_confidence("Agents had divided opinions") == "low"


# ---------------------------------------------------------------------------
# Regex extraction -- key factors
# ---------------------------------------------------------------------------


class TestExtractKeyFactors:
    def test_dash_list(self, parser):
        text = "Key factors:\n- factor 1\n- factor 2"
        assert parser._extract_key_factors(text) == ["factor 1", "factor 2"]

    def test_numbered_list(self, parser):
        text = "Key Factors:\n1) factor 1\n2) factor 2"
        assert parser._extract_key_factors(text) == ["factor 1", "factor 2"]

    def test_no_header(self, parser):
        text = "Some report without a key factors header."
        assert parser._extract_key_factors(text) == []

    def test_max_five_factors(self, parser):
        items = "\n".join(f"- item {i}" for i in range(10))
        text = f"Key factors:\n{items}"
        result = parser._extract_key_factors(text)
        assert len(result) == 5

    def test_star_bullet(self, parser):
        text = "Key factors:\n* alpha\n* beta"
        assert parser._extract_key_factors(text) == ["alpha", "beta"]

    def test_driving_factors_header(self, parser):
        text = "Driving Factors:\n- a\n- b"
        assert parser._extract_key_factors(text) == ["a", "b"]


# ---------------------------------------------------------------------------
# parse method
# ---------------------------------------------------------------------------


class TestParse:
    @pytest.mark.asyncio
    async def test_regex_path(self, parser):
        report = "The 65% probability is based on high confidence.\nKey factors:\n- momentum"
        pred = await parser.parse(report, "Will X happen?")
        assert pred.probability == 0.65
        assert pred.confidence == "high"
        assert pred.extraction_method == "regex"
        assert "momentum" in pred.key_factors

    @pytest.mark.asyncio
    async def test_fallback_to_llm(self, parser):
        """When regex fails and no API key, returns default prediction."""
        report = "The report is ambiguous and contains no clear number."
        pred = await parser.parse(report, "Will X happen?")
        assert pred.probability == 0.5
        assert pred.confidence == "low"
        assert pred.extraction_method == "llm"

    @pytest.mark.asyncio
    async def test_empty_report_raises(self, parser):
        with pytest.raises(ValueError, match="report_text must be a non-empty string"):
            await parser.parse("", "Will X happen?")

    @pytest.mark.asyncio
    async def test_whitespace_only_report_raises(self, parser):
        with pytest.raises(ValueError, match="report_text must be a non-empty string"):
            await parser.parse("   \n  ", "Will X happen?")

    @pytest.mark.asyncio
    async def test_none_report_raises(self, parser):
        with pytest.raises((ValueError, TypeError)):
            await parser.parse(None, "Will X happen?")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LLM extraction (mock httpx)
# ---------------------------------------------------------------------------


def _make_llm_response(probability=0.72, confidence="high", key_factors=None):
    """Build a fake OpenAI JSON response."""
    content = json.dumps(
        {
            "probability": probability,
            "confidence": confidence,
            "key_factors": key_factors or ["factor A", "factor B"],
        }
    )
    return {
        "choices": [{"message": {"content": content}}],
    }


class TestLLMExtraction:
    @pytest.mark.asyncio
    async def test_valid_json_response(self, parser_with_key):
        mock_response = httpx.Response(
            200,
            json=_make_llm_response(0.72, "high", ["a", "b", "c"]),
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        with patch("polymarket_predictor.parser.prediction.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            report = "A vague report with no numbers."
            pred = await parser_with_key.parse(report, "Will X happen?")
            assert pred.probability == 0.72
            assert pred.confidence == "high"
            assert pred.extraction_method == "llm"
            assert pred.key_factors == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_api_error_returns_default(self, parser_with_key):
        with patch("polymarket_predictor.parser.prediction.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.side_effect = httpx.HTTPStatusError(
                "500",
                request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
                response=httpx.Response(500),
            )
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            report = "A report with no clear probability."
            pred = await parser_with_key.parse(report, "Will X happen?")
            assert pred.probability == 0.5
            assert pred.confidence == "low"
            assert pred.extraction_method == "llm"

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_default(self, parser):
        report = "A report with no clear probability."
        pred = await parser.parse(report, "Will X happen?")
        assert pred.probability == 0.5
        assert pred.confidence == "low"
        assert "no API key" in pred.key_factors[0]

    @pytest.mark.asyncio
    async def test_malformed_json_returns_default(self, parser_with_key):
        mock_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not valid json {{"}}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        with patch("polymarket_predictor.parser.prediction.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            report = "Ambiguous report."
            pred = await parser_with_key.parse(report, "Will X happen?")
            assert pred.probability == 0.5
            assert pred.confidence == "low"

    @pytest.mark.asyncio
    async def test_probability_clamped_to_0_1(self, parser_with_key):
        mock_response = httpx.Response(
            200,
            json=_make_llm_response(1.5, "medium"),
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        with patch("polymarket_predictor.parser.prediction.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            report = "Ambiguous report."
            pred = await parser_with_key.parse(report, "Will X happen?")
            assert pred.probability == 1.0
