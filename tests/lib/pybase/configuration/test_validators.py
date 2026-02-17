"""Tests for the configuration model validators."""

import pytest
from buvis.pybase.configuration import (
    MAX_JSON_ENV_SIZE,
    MAX_NESTING_DEPTH,
    get_model_depth,
    validate_json_env_size,
    validate_nesting_depth,
)
from buvis.pybase.configuration.validators import _iter_model_types
from pydantic import BaseModel


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
        from buvis.pybase.configuration import SecureSettingsMixin
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class TestSettings(SecureSettingsMixin, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_SECURE_")
            value: str = ""

        oversized = "x" * (MAX_JSON_ENV_SIZE + 1)
        monkeypatch.setenv("TEST_SECURE_VALUE", oversized)

        with pytest.raises(ValueError, match="exceeds max JSON size"):
            TestSettings()

    def test_allows_valid_sized_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid-sized prefixed env var is allowed."""
        from buvis.pybase.configuration import SecureSettingsMixin
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class TestSettings(SecureSettingsMixin, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_SECURE_")
            value: str = ""

        valid = "x" * 100
        monkeypatch.setenv("TEST_SECURE_VALUE", valid)

        settings = TestSettings()

        assert settings.value == valid

    def test_ignores_non_prefixed_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Oversized non-prefixed env var is allowed."""
        from buvis.pybase.configuration import SecureSettingsMixin
        from pydantic_settings import BaseSettings, SettingsConfigDict

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
        from buvis.pybase.configuration import SafeLoggingMixin
        from pydantic_settings import BaseSettings

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
        from buvis.pybase.configuration import SafeLoggingMixin
        from pydantic_settings import BaseSettings

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
        from buvis.pybase.configuration import SafeLoggingMixin
        from pydantic_settings import BaseSettings

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
        from buvis.pybase.configuration import SafeLoggingMixin
        from pydantic_settings import BaseSettings

        class TestSettings(SafeLoggingMixin, BaseSettings):
            username: str = "bob"
            email: str = "bob@example.com"
            count: int = 42

        settings = TestSettings()
        result = repr(settings)

        assert "username='bob'" in result
        assert "email='bob@example.com'" in result
        assert "count=42" in result


class _Inner(BaseModel):
    value: str


class _Outer(BaseModel):
    child: _Inner | None


class _Item(BaseModel):
    name: str


class _Container(BaseModel):
    items: list[_Item]


class _Value(BaseModel):
    data: int


class _Registry(BaseModel):
    entries: dict[str, _Value]


class _Shared(BaseModel):
    x: int


class _Wrapper(BaseModel):
    child: _Shared


class _Multi(BaseModel):
    a: _Wrapper
    b: _Wrapper | None


class TestIterModelTypes:
    """Tests for _iter_model_types helper function."""

    def test_handles_union_type_with_nested_models(self) -> None:
        models = list(_iter_model_types(_Outer.model_fields["child"].annotation))
        assert _Inner in models

    def test_handles_list_of_models(self) -> None:
        models = list(_iter_model_types(_Container.model_fields["items"].annotation))
        assert _Item in models

    def test_handles_dict_with_model_values(self) -> None:
        models = list(_iter_model_types(_Registry.model_fields["entries"].annotation))
        assert _Value in models

    def test_deduplicates_seen_models(self) -> None:
        models = list(_iter_model_types(_Multi.model_fields["b"].annotation))
        assert models.count(_Wrapper) == 1

    def test_non_generic_non_model_type_skipped(self) -> None:
        models = list(_iter_model_types(str))
        assert models == []

    def test_none_origin_skips_processing(self) -> None:
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
