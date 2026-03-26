"""Tests for the settings endpoints in polymarket_predictor.dashboard.api."""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from flask import Flask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_stage_config(*_args, **_kwargs):
    return {
        "model": "gpt-4o",
        "api_key": "sk-xxx",
        "price_input": 2.50,
        "price_output": 10.00,
    }


def _build_app(tmp_path):
    """Create a Flask app with the dashboard blueprint, fully mocked."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from polymarket_predictor.dashboard.api import dashboard_bp
    # Re-register is fine for a fresh app object
    app.register_blueprint(dashboard_bp)
    return app


@pytest.fixture
def client(tmp_path):
    """Flask test client with mocked dependencies."""
    with patch("polymarket_predictor.dashboard.api.DATA_DIR", tmp_path), \
         patch("polymarket_predictor.dashboard.api._SETTINGS_PATH", tmp_path / "settings.json"):
        app = _build_app(tmp_path)
        yield app.test_client()


def _patch_settings_get():
    """Context manager that patches all dependencies of settings_get."""
    mock_ap = MagicMock()
    mock_ap.get_config.return_value = {"max_rounds": 5}

    mock_strat = MagicMock()
    mock_strat.get_config.return_value = {"min_edge": 0.05}

    mock_tracker = MagicMock()
    mock_tracker.llm_weight = 0.4
    mock_tracker.quant_weight = 0.6

    class PatchContext:
        def __enter__(self_inner):
            self_inner._patches = [
                patch("polymarket_predictor.dashboard.api._get_autopilot", return_value=mock_ap),
                patch("polymarket_predictor.dashboard.api.get_stage_config", side_effect=_mock_stage_config),
                patch("polymarket_predictor.dashboard.api._PRESETS", {"default": {"ontology": "gpt-4o"}}),
                patch("polymarket_predictor.dashboard.api.PIPELINE_PRESET", "default"),
                # Patch at the source module so lazy imports pick them up
                patch("polymarket_predictor.optimizer.strategy.StrategyOptimizer", return_value=mock_strat),
                patch("polymarket_predictor.analyzer.method_tracker.MethodTracker", return_value=mock_tracker),
            ]
            for p in self_inner._patches:
                p.start()
            return self_inner

        def __exit__(self_inner, *args):
            for p in self_inner._patches:
                p.stop()

    return PatchContext()


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


class TestGetSettings:

    def test_get_settings_returns_200(self, client):
        """GET /settings returns 200."""
        with _patch_settings_get():
            resp = client.get("/api/polymarket/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "data" in data

    def test_get_settings_returns_all_sections(self, client):
        """Response has autopilot, pipeline, strategy, api_keys sections."""
        with _patch_settings_get():
            resp = client.get("/api/polymarket/settings")

        result = resp.get_json()["data"]
        assert "autopilot" in result
        assert "pipeline_stages" in result
        assert "strategy" in result
        assert "api_keys" in result
        assert "method_weights" in result

    def test_api_keys_never_exposed(self, client):
        """Response has boolean has_key indicators, never actual key values."""
        with _patch_settings_get(), \
             patch.dict(os.environ, {"LLM_API_KEY": "sk-secret-key-12345", "DEEPSEEK_API_KEY": ""}, clear=False):
            resp = client.get("/api/polymarket/settings")

        data = resp.get_json()["data"]

        # api_keys section should have booleans, not actual keys
        api_keys = data["api_keys"]
        assert isinstance(api_keys["openai"], bool)
        assert api_keys["openai"] is True  # LLM_API_KEY was set
        assert api_keys["deepseek"] is False  # DEEPSEEK_API_KEY was empty

        # The full response should not contain the actual secret key
        response_text = json.dumps(data)
        assert "sk-secret-key-12345" not in response_text

        # pipeline_stages has has_api_key boolean, not the raw key
        for stage_info in data["pipeline_stages"].values():
            assert "has_api_key" in stage_info
            assert isinstance(stage_info["has_api_key"], bool)


# ---------------------------------------------------------------------------
# PUT /settings
# ---------------------------------------------------------------------------


class TestPutSettings:

    def test_put_settings_updates_custom(self, client, tmp_path):
        """Change a custom setting value, verify it persists."""
        settings_path = tmp_path / "settings.json"

        with patch("polymarket_predictor.dashboard.api._SETTINGS_PATH", settings_path), \
             patch("polymarket_predictor.dashboard.api.push_log"):

            # Write initial empty settings
            settings_path.write_text("{}")

            resp = client.put(
                "/api/polymarket/settings",
                json={"custom": {"max_rounds": 10, "new_param": "value"}},
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify the file was updated
        saved = json.loads(settings_path.read_text())
        assert saved["max_rounds"] == 10
        assert saved["new_param"] == "value"

    def test_put_settings_invalid_key_ignored(self, client):
        """Unknown top-level key doesn't crash."""
        with patch("polymarket_predictor.dashboard.api.push_log"):
            resp = client.put(
                "/api/polymarket/settings",
                json={"unknown_section": {"foo": "bar"}},
                content_type="application/json",
            )
        assert resp.status_code == 200

    def test_put_settings_empty_body(self, client):
        """Empty body returns 400."""
        resp = client.put(
            "/api/polymarket/settings",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400
