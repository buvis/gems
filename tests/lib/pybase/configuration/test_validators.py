"""Tests for the configuration model validators."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from buvis.pybase.configuration import (
    MAX_JSON_ENV_SIZE,
    MAX_NESTING_DEPTH,
    get_model_depth,
    validate_json_env_size,
    validate_nesting_depth,
)
from buvis.pybase.configuration.validators import _iter_model_types


class Level0Valid(BaseModel):
    value: str = "leaf"


class Level1(BaseModel):
    child: Level0Valid


class Level2(BaseModel):
    child: Level1


class Level3(BaseModel):
    child: Level2


class Level4(BaseModel):
    child: Level3


class Level5(BaseModel):
    child: Level4


class Level6Invalid(BaseModel):
    child: Level5


class TestGetModelDepth:
    def test_flat_model_depth_zero(self) -> None:
        assert get_model_depth(Level0Valid) == 0

    def test_nested_model_depth_five(self) -> None:
        assert get_model_depth(Level5) == MAX_NESTING_DEPTH

    def test_nested_model_depth_six(self) -> None:
        assert get_model_depth(Level6Invalid) == MAX_NESTING_DEPTH + 1


class TestValidateNestingDepth:
    def test_valid_depth_passes(self) -> None:
        validate_nesting_depth(Level5)

    def test_invalid_depth_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            validate_nesting_depth(Level6Invalid)


class TestMaxJsonEnvSizeConstant:
    def test_max_json_env_size_equals_expected_value(self) -> None:
        assert MAX_JSON_ENV_SIZE == 64 * 1024


class TestValidateJsonEnvSize:
    def test_passes_for_empty_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env_var = "TEST_JSON_ENV"
        monkeypatch.delenv(env_var, raising=False)

        validate_json_env_size(env_var)

    def test_passes_at_exact_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env_var = "TEST_JSON_ENV"
        payload = "a" * MAX_JSON_ENV_SIZE
        monkeypatch.setenv(env_var, payload)

        validate_json_env_size(env_var)

    def test_raises_over_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env_var = "TEST_JSON_ENV"
        payload = "a" * (MAX_JSON_ENV_SIZE + 1)
        monkeypatch.setenv(env_var, payload)

        with pytest.raises(ValueError):
            validate_json_env_size(env_var)

    def test_utf8_multibyte_chars_counted_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env_var = "TEST_JSON_ENV"
        multibyte_char = "é"
        payload = multibyte_char * (MAX_JSON_ENV_SIZE // len(multibyte_char.encode("utf-8")))
        monkeypatch.setenv(env_var, payload)

        validate_json_env_size(env_var)

        payload_over = payload + multibyte_char
        monkeypatch.setenv(env_var, payload_over)

        with pytest.raises(ValueError):
            validate_json_env_size(env_var)


class TestSecureSettingsMixin:
    def test_validates_oversized_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Oversized prefixed env var raises ValueError."""
        from pydantic_settings import BaseSettings, SettingsConfigDict

        from buvis.pybase.configuration import SecureSettingsMixin

        class TestSettings(SecureSettingsMixin, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_SECURE_")
            value: str = ""

        oversized = "x" * (MAX_JSON_ENV_SIZE + 1)
        monkeypatch.setenv("TEST_SECURE_VALUE", oversized)

        with pytest.raises(ValueError, match="exceeds max JSON size"):
            TestSettings()

    def test_allows_valid_sized_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid-sized prefixed env var is allowed."""
        from pydantic_settings import BaseSettings, SettingsConfigDict

        from buvis.pybase.configuration import SecureSettingsMixin

        class TestSettings(SecureSettingsMixin, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_SECURE_")
            value: str = ""

        valid = "x" * 100
        monkeypatch.setenv("TEST_SECURE_VALUE", valid)

        settings = TestSettings()

        assert settings.value == valid

    def test_ignores_non_prefixed_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Oversized non-prefixed env var is allowed."""
        from pydantic_settings import BaseSettings, SettingsConfigDict

        from buvis.pybase.configuration import SecureSettingsMixin

        class TestSettings(SecureSettingsMixin, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_SECURE_")
            value: str = "default"

        oversized = "x" * (MAX_JSON_ENV_SIZE + 1)
        monkeypatch.setenv("OTHER_VAR", oversized)

        settings = TestSettings()  # Should not raise

        assert settings.value == "default"


class TestSafeLoggingMixin:
    def test_masks_sensitive_scalar_field(self) -> None:
        """Scalar field with sensitive name is masked in repr."""
        from pydantic_settings import BaseSettings

        from buvis.pybase.configuration import SafeLoggingMixin

        class TestSettings(SafeLoggingMixin, BaseSettings):
            api_key: str = "secret123"
            name: str = "public"

        settings = TestSettings()
        result = repr(settings)

        assert "api_key='***'" in result
        assert "name='public'" in result
        assert "secret123" not in result

    def test_masks_sensitive_dict_keys(self) -> None:
        """Dict values with sensitive keys are masked."""
        from pydantic_settings import BaseSettings

        from buvis.pybase.configuration import SafeLoggingMixin

        class TestSettings(SafeLoggingMixin, BaseSettings):
            headers: dict[str, str] = {
                "Authorization": "Bearer xyz",
                "Content-Type": "json",
            }

        settings = TestSettings()
        result = repr(settings)

        assert "'Authorization': '***'" in result
        assert "'Content-Type': 'json'" in result
        assert "Bearer xyz" not in result

    def test_various_sensitive_patterns(self) -> None:
        """Various sensitive field names are masked."""
        from pydantic_settings import BaseSettings

        from buvis.pybase.configuration import SafeLoggingMixin

        class TestSettings(SafeLoggingMixin, BaseSettings):
            password: str = "pass123"
            token: str = "tok456"
            secret: str = "sec789"
            bearer: str = "bear000"

        settings = TestSettings()
        result = repr(settings)

        assert "password='***'" in result
        assert "token='***'" in result
        assert "secret='***'" in result
        assert "bearer='***'" in result

    def test_non_sensitive_fields_shown(self) -> None:
        """Non-sensitive fields are shown normally."""
        from pydantic_settings import BaseSettings

        from buvis.pybase.configuration import SafeLoggingMixin

        class TestSettings(SafeLoggingMixin, BaseSettings):
            username: str = "bob"
            email: str = "bob@example.com"
            count: int = 42

        settings = TestSettings()
        result = repr(settings)

        assert "username='bob'" in result
        assert "email='bob@example.com'" in result
        assert "count=42" in result


class TestIterModelTypes:
    """Tests for _iter_model_types helper function."""

    def test_handles_union_type_with_nested_models(self) -> None:
        """Lines 47-51: Process Union types containing BaseModel."""

        class Inner(BaseModel):
            value: str

        class Outer(BaseModel):
            child: Inner | None

        models = list(_iter_model_types(Outer.model_fields["child"].annotation))
        assert Inner in models

    def test_handles_list_of_models(self) -> None:
        """Extracts models from list[Model] annotations."""

        class Item(BaseModel):
            name: str

        class Container(BaseModel):
            items: list[Item]

        models = list(_iter_model_types(Container.model_fields["items"].annotation))
        assert Item in models

    def test_handles_dict_with_model_values(self) -> None:
        """Extracts models from dict[str, Model] annotations."""

        class Value(BaseModel):
            data: int

        class Registry(BaseModel):
            entries: dict[str, Value]

        models = list(_iter_model_types(Registry.model_fields["entries"].annotation))
        assert Value in models

    def test_deduplicates_seen_models(self) -> None:
        """Same model appearing multiple times is only yielded once per call."""

        class Shared(BaseModel):
            x: int

        class Wrapper(BaseModel):
            child: Shared

        class Multi(BaseModel):
            a: Wrapper
            b: Wrapper | None

        # Within a single Union, models are deduplicated
        models = list(_iter_model_types(Multi.model_fields["b"].annotation))
        # Wrapper appears once even though it's in the Union
        assert models.count(Wrapper) == 1

    def test_non_generic_non_model_type_skipped(self) -> None:
        """Plain types like str, int are skipped (lines 47-48)."""
        models = list(_iter_model_types(str))
        assert models == []

    def test_none_origin_skips_processing(self) -> None:
        """Non-generic types without origin are skipped."""
        models = list(_iter_model_types(int))
        assert models == []


class TestIsSensitiveField:
    """Tests for is_sensitive_field function."""

    def test_password_is_sensitive(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("password") is True
        assert is_sensitive_field("database_password") is True
        assert is_sensitive_field("PASSWORD") is True

    def test_api_key_is_sensitive(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("api_key") is True
        assert is_sensitive_field("apikey") is True
        assert is_sensitive_field("api-key") is True
        assert is_sensitive_field("API_KEY") is True

    def test_token_is_sensitive(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("token") is True
        assert is_sensitive_field("auth_token") is True
        assert is_sensitive_field("access_token") is True

    def test_secret_is_sensitive(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("secret") is True
        assert is_sensitive_field("client_secret") is True

    def test_nested_path_is_sensitive(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("database.password") is True
        assert is_sensitive_field("auth.api_key") is True
        assert is_sensitive_field("services.redis.token") is True

    def test_non_sensitive_fields(self) -> None:
        from buvis.pybase.configuration import is_sensitive_field

        assert is_sensitive_field("debug") is False
        assert is_sensitive_field("username") is False
        assert is_sensitive_field("host") is False
        assert is_sensitive_field("database.host") is False
        assert is_sensitive_field("log_level") is False
