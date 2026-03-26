"""Test Gemini model configuration and fallback."""
import pytest
from polymarket_predictor.config import MODEL_PRICING, _PRESETS, get_stage_config, PROVIDER_DEFAULTS


class TestGeminiConfig:
    def test_gemini_model_in_pricing(self):
        """At least one Gemini model should be in the pricing table."""
        gemini_models = [k for k in MODEL_PRICING if "gemini" in k.lower()]
        assert len(gemini_models) >= 1, "No Gemini models in MODEL_PRICING"

    def test_balanced_preset_profiles_model_in_pricing(self):
        """The profiles model in 'balanced' preset should exist in pricing."""
        profiles_model = _PRESETS["balanced"]["profiles"]
        assert profiles_model in MODEL_PRICING, f"Profiles model '{profiles_model}' not in MODEL_PRICING"

    def test_gemini_preset_all_models_in_pricing(self):
        """All models in 'gemini' preset should exist in pricing."""
        if "gemini" in _PRESETS:
            for stage, model in _PRESETS["gemini"].items():
                assert model in MODEL_PRICING, f"Gemini preset stage '{stage}' uses '{model}' not in MODEL_PRICING"

    def test_get_stage_config_has_base_url(self):
        """Stage config for profiles should include a base_url."""
        cfg = get_stage_config("profiles")
        assert "base_url" in cfg
        assert cfg["base_url"], "base_url should not be empty"

    def test_gemini_provider_base_url(self):
        """Gemini provider should use the correct API base URL."""
        if "gemini" in PROVIDER_DEFAULTS:
            assert "generativelanguage.googleapis.com" in PROVIDER_DEFAULTS["gemini"]["base_url"]

    def test_fallback_preset_works_without_gemini(self):
        """If Gemini key is missing, the 'budget' preset avoids Gemini entirely."""
        for stage, model in _PRESETS["budget"].items():
            # Budget preset should NOT use Gemini
            assert "gemini" not in model.lower(), f"Budget preset shouldn't use Gemini for {stage}"

    def test_no_deprecated_models_in_active_presets(self):
        """Active presets should not reference deprecated gemini-2.0 models."""
        deprecated = {"gemini-2.0-flash", "gemini-2.0-flash-lite"}
        for preset_name, preset in _PRESETS.items():
            for stage, model in preset.items():
                assert model not in deprecated, (
                    f"Preset '{preset_name}' stage '{stage}' uses deprecated model '{model}'. "
                    f"Use gemini-2.5-flash-lite instead."
                )

    def test_gemini_25_flash_lite_in_pricing(self):
        """gemini-2.5-flash-lite should be in the pricing table."""
        assert "gemini-2.5-flash-lite" in MODEL_PRICING, "gemini-2.5-flash-lite missing from MODEL_PRICING"
        assert MODEL_PRICING["gemini-2.5-flash-lite"]["provider"] == "gemini"
