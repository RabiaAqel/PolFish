"""Extract structured predictions from MiroFish report markdown text.

Supports two extraction strategies:
1. Regex-based parsing for well-formatted reports (fast, no API call).
2. LLM-based extraction as a fallback for ambiguous or free-form reports.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from polymarket_predictor.config import LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Prediction:
    """A structured prediction extracted from a MiroFish simulation report."""

    probability: float  # 0.0 to 1.0 (probability of "Yes" outcome)
    confidence: str  # "high", "medium", "low"
    key_factors: list[str]  # Top reasons driving the prediction
    raw_report: str  # Full report markdown
    extraction_method: str  # "regex" or "llm"


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Matches patterns like "65% probability", "65% likely", "65% chance",
# "probability of 65%", "likelihood of 65%", "estimated at 65%",
# "approximately 65%", "Yes: 65%", "Yes outcome: 65%"
_PROBABILITY_PATTERNS: list[re.Pattern[str]] = [
    # HIGHEST PRIORITY: Prediction Verdict format from MiroFish report
    # "Probability of YES outcome: X%" or "- Probability of YES outcome: X%"
    re.compile(
        r"Probability\s+of\s+YES\s+outcome\s*:\s*(\d{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
    # "X% probability / likely / chance"
    re.compile(
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:probability|likely|likelihood|chance)",
        re.IGNORECASE,
    ),
    # "probability / likelihood of X%"
    re.compile(
        r"(?:probability|likelihood)\s+of\s+(\d{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
    # "estimated at X%" / "approximately X%"
    re.compile(
        r"(?:estimated\s+at|approximately)\s+(\d{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
    # "Yes: X%" / "Yes outcome: X%"
    re.compile(
        r"Yes(?:\s+outcome)?\s*:\s*(\d{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
]

# Default LLM probabilities to flag as low-quality
_DEFAULT_PROBABILITIES = {0.25, 0.35, 0.50, 0.65, 0.75}

_HIGH_CONFIDENCE_KEYWORDS = re.compile(
    r"high\s+confidence|strong\s+consensus|very\s+likely|highly\s+confident",
    re.IGNORECASE,
)
_LOW_CONFIDENCE_KEYWORDS = re.compile(
    r"low\s+confidence|uncertain|divided\s+opinions|highly\s+uncertain|unclear",
    re.IGNORECASE,
)
_MEDIUM_CONFIDENCE_KEYWORDS = re.compile(
    r"medium\s+confidence|moderate\s+confidence|somewhat\s+confident|mixed\s+signals",
    re.IGNORECASE,
)

# Matches a section header related to key factors, then captures subsequent
# bullet / numbered list items.
_KEY_FACTORS_HEADER = re.compile(
    r"(?:key\s+factors|main\s+drivers|primary\s+reasons|driving\s+factors|key\s+drivers)",
    re.IGNORECASE,
)
_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)]\s)\s*(.+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class PredictionParser:
    """Extract a :class:`Prediction` from a MiroFish simulation report.

    The parser first attempts fast regex-based extraction.  If regex fails or
    returns ambiguous results it falls back to an LLM call (OpenAI-compatible
    API).
    """

    def __init__(
        self,
        llm_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
    ) -> None:
        self.llm_api_key: str = llm_api_key or LLM_API_KEY
        self.llm_model: str = llm_model or LLM_MODEL

    # -- public API ---------------------------------------------------------

    async def parse(
        self,
        report_text: str,
        market_question: str,
    ) -> Prediction:
        """Return a structured :class:`Prediction` from *report_text*.

        Parameters
        ----------
        report_text:
            Full markdown text of a MiroFish simulation report.
        market_question:
            The Polymarket question the report addresses.
        """
        if not report_text or not report_text.strip():
            raise ValueError("report_text must be a non-empty string")

        # 1) Try regex first
        prediction = self._parse_with_regex(report_text)
        if prediction is not None:
            logger.info(
                "Regex extraction succeeded (probability=%.2f, confidence=%s)",
                prediction.probability,
                prediction.confidence,
            )
            return prediction

        logger.info("Regex extraction failed or was ambiguous; falling back to LLM")

        # 2) Fall back to LLM
        prediction = await self._parse_with_llm(report_text, market_question)

        # 3) Quality check: flag default LLM probabilities
        rounded = round(prediction.probability, 2)
        if rounded in _DEFAULT_PROBABILITIES:
            logger.warning(
                "Prediction %.2f looks like an LLM default — marking as low confidence",
                prediction.probability,
            )
            prediction.confidence = "low"

        return prediction

    # -- regex extraction ---------------------------------------------------

    def _parse_with_regex(self, report_text: str) -> Prediction | None:
        """Attempt to extract a prediction using regular expressions.

        Returns ``None`` when no clear probability can be found.
        """
        probability = self._extract_probability(report_text)
        if probability is None:
            return None

        confidence = self._extract_confidence(report_text)
        key_factors = self._extract_key_factors(report_text)

        return Prediction(
            probability=probability,
            confidence=confidence,
            key_factors=key_factors,
            raw_report=report_text,
            extraction_method="regex",
        )

    @staticmethod
    def _extract_probability(text: str) -> float | None:
        """Return the first probability value found in *text* as a float in [0, 1].

        Returns ``None`` when nothing matches or the value is out of range.
        """
        for pattern in _PROBABILITY_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    value = float(match.group(1))
                except (ValueError, IndexError):
                    continue
                if 0.0 <= value <= 100.0:
                    return round(value / 100.0, 4)
        return None

    @staticmethod
    def _extract_confidence(text: str) -> str:
        """Infer confidence level from language cues in *text*."""
        if _HIGH_CONFIDENCE_KEYWORDS.search(text):
            return "high"
        if _LOW_CONFIDENCE_KEYWORDS.search(text):
            return "low"
        if _MEDIUM_CONFIDENCE_KEYWORDS.search(text):
            return "medium"
        # Default when no explicit signal is found
        return "medium"

    @staticmethod
    def _extract_key_factors(text: str) -> list[str]:
        """Extract bullet/numbered items near a *key factors* header."""
        header_match = _KEY_FACTORS_HEADER.search(text)
        if not header_match:
            return []

        # Grab the text block following the header (up to 2000 chars)
        start = header_match.end()
        block = text[start : start + 2000]

        factors: list[str] = []
        for item_match in _LIST_ITEM.finditer(block):
            factor = item_match.group(1).strip()
            if factor:
                factors.append(factor)
            # Stop after collecting enough items to avoid unrelated lists
            if len(factors) >= 5:
                break

        return factors

    # -- LLM extraction -----------------------------------------------------

    async def _parse_with_llm(
        self,
        report_text: str,
        market_question: str,
    ) -> Prediction:
        """Use an OpenAI-compatible API to extract a prediction."""
        if not self.llm_api_key:
            logger.warning(
                "No LLM API key configured; returning default uncertain prediction"
            )
            return Prediction(
                probability=0.5,
                confidence="low",
                key_factors=["LLM extraction unavailable (no API key)"],
                raw_report=report_text,
                extraction_method="llm",
            )

        system_prompt = (
            "You are a prediction extraction assistant. "
            "Given a simulation report about a prediction market question, extract: "
            "1) The predicted probability of the 'Yes' outcome (0.0 to 1.0), "
            "2) Confidence level (high/medium/low), "
            "3) Top 3 key factors. "
            'Respond in JSON format: {"probability": 0.65, "confidence": "medium", '
            '"key_factors": ["factor1", "factor2", "factor3"]}'
        )

        user_message = (
            f"Market question: {market_question}\n\n"
            f"Report:\n{report_text[:4000]}"
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            probability = float(parsed.get("probability", 0.5))
            probability = max(0.0, min(1.0, probability))

            confidence = parsed.get("confidence", "medium")
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"

            key_factors = parsed.get("key_factors", [])
            if not isinstance(key_factors, list):
                key_factors = []
            key_factors = [str(f) for f in key_factors[:5]]

            logger.info(
                "LLM extraction succeeded (probability=%.2f, confidence=%s)",
                probability,
                confidence,
            )

            return Prediction(
                probability=probability,
                confidence=confidence,
                key_factors=key_factors,
                raw_report=report_text,
                extraction_method="llm",
            )

        except httpx.HTTPStatusError as exc:
            logger.error("LLM API HTTP error: %s", exc)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to parse LLM response: %s", exc)
        except httpx.RequestError as exc:
            logger.error("LLM API request failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error during LLM extraction: %s", exc)

        # Fallback on any error
        return Prediction(
            probability=0.5,
            confidence="low",
            key_factors=["LLM extraction failed"],
            raw_report=report_text,
            extraction_method="llm",
        )
