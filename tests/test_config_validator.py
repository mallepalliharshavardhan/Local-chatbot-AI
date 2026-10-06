import pytest

from main import ConfigError, ConfigValidator


def test_ollama_does_not_require_cloud_api_key(tmp_path):
    secrets_path = tmp_path / "secrets.yaml"
    secrets_path.write_text("{}", encoding="utf-8")

    assert ConfigValidator.validate_secrets(secrets_path, "ollama") == ""


def test_cloud_model_still_requires_api_key(tmp_path):
    secrets_path = tmp_path / "secrets.yaml"
    secrets_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing secret"):
        ConfigValidator.validate_secrets(secrets_path, "openai")
