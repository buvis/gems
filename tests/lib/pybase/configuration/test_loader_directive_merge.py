from __future__ import annotations

import logging

import pytest
from buvis.pybase.configuration.exceptions import ConfigurationError
from buvis.pybase.configuration.loader import ConfigurationLoader


class TestDirectiveAppend:
    """`key+` appends to a list, order-preserving with dedup."""

    def test_append_seeds_when_base_absent(self) -> None:
        result = ConfigurationLoader.merge_configs({"excludes+": ["a", "b"]})

        assert result == {"excludes": ["a", "b"]}

    def test_append_extends_existing_list(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["node_modules", "__pycache__"]},
            {"excludes+": [".terraform"]},
        )

        assert result == {"excludes": ["node_modules", "__pycache__", ".terraform"]}

    def test_append_is_order_preserving_and_dedups(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b"]},
            {"excludes+": ["b", "c", "b"]},
        )

        assert result == {"excludes": ["a", "b", "c"]}


class TestDirectiveRemove:
    """`key-` removes items; absent items are a no-op."""

    def test_remove_existing_item(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b", "c"]},
            {"excludes-": ["b"]},
        )

        assert result == {"excludes": ["a", "c"]}

    def test_remove_absent_item_is_noop(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b"]},
            {"excludes-": ["zzz"]},
        )

        assert result == {"excludes": ["a", "b"]}


class TestSameLayerOrdering:
    """Within one layer, `+` applies then `-` (removal wins)."""

    def test_add_then_remove_same_token_nets_to_removed(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a"]},
            {"excludes+": ["b"], "excludes-": ["b"]},
        )

        assert result == {"excludes": ["a"]}

    def test_order_independent_within_layer(self) -> None:
        # Same directives, opposite dict insertion order -> same result.
        layer_a = {"excludes+": ["b"], "excludes-": ["a"]}
        layer_b = {"excludes-": ["a"], "excludes+": ["b"]}
        base = {"excludes": ["a"]}

        assert ConfigurationLoader.merge_configs(dict(base), layer_a) == {"excludes": ["b"]}
        assert ConfigurationLoader.merge_configs(dict(base), layer_b) == {"excludes": ["b"]}


class TestPlainKeyReset:
    """A plain `key` in a later layer resets accumulated append/remove history."""

    def test_plain_key_resets_accumulated_list(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b"]},
            {"excludes+": ["c"]},
            {"excludes": ["x"]},
        )

        assert result == {"excludes": ["x"]}

    def test_plain_reset_then_same_layer_directives(self) -> None:
        # Within the resetting layer, plain reset applies first, then +/-.
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b"]},
            {"excludes": ["x"], "excludes+": ["y"], "excludes-": ["x"]},
        )

        assert result == {"excludes": ["y"]}


class TestThreeLayerAccumulation:
    """The PRD's canonical three-layer example resolves as documented."""

    def test_prd_excludes_example(self) -> None:
        gem = {"excludes": ["node_modules", "__pycache__", ".venv"]}
        user = {"excludes+": [".terraform", ".gradle"]}
        machine = {"excludes+": [".cache"], "excludes-": [".venv"]}

        result = ConfigurationLoader.merge_configs(gem, user, machine)

        assert result == {
            "excludes": ["node_modules", "__pycache__", ".terraform", ".gradle", ".cache"],
        }


class TestNonListBaseError:
    """A directive over a non-list base is a loader error, not a coercion."""

    def test_append_over_scalar_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            ConfigurationLoader.merge_configs(
                {"excludes": "not-a-list"},
                {"excludes+": ["a"]},
            )

    def test_remove_over_dict_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            ConfigurationLoader.merge_configs(
                {"excludes": {"a": 1}},
                {"excludes-": ["a"]},
            )


class TestDirectiveStripping:
    """Directive keys never appear in the merged output."""

    def test_no_directive_keys_in_result(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a"]},
            {"excludes+": ["b"], "excludes-": ["a"]},
        )

        assert "excludes+" not in result
        assert "excludes-" not in result
        assert set(result) == {"excludes"}

    def test_extra_forbid_models_see_only_plain_keys(self) -> None:
        # Simulate a strict Pydantic model: merged output must contain only the
        # plain key so a model with extra="forbid" would not choke on 'excludes+'.
        merged = ConfigurationLoader.merge_configs(
            {"excludes": ["a"]},
            {"excludes+": ["b"]},
        )

        assert all(not k.endswith(("+", "-")) for k in merged)


class TestPlainKeyRegression:
    """Plain (undirected) keys replace exactly as before."""

    def test_plain_list_replaces_wholesale(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"excludes": ["a", "b", "c"]},
            {"excludes": ["x"]},
        )

        assert result == {"excludes": ["x"]}

    def test_nested_dict_still_recurses(self) -> None:
        result = ConfigurationLoader.merge_configs(
            {"tool": {"a": 1, "b": 2}},
            {"tool": {"b": 3, "c": 4}},
        )

        assert result == {"tool": {"a": 1, "b": 3, "c": 4}}

    def test_scalar_replaces(self) -> None:
        result = ConfigurationLoader.merge_configs({"n": 1}, {"n": 2})

        assert result == {"n": 2}


class TestBareDirectiveKeyIsPlain:
    """A bare '+' or '-' key has no base to target and stays a plain key."""

    def test_bare_plus_key_is_literal(self) -> None:
        result = ConfigurationLoader.merge_configs({"+": ["a"]})

        assert result == {"+": ["a"]}


class TestTypoGuard:
    """`known_keys` warns on a directive targeting an unknown base key."""

    def test_unknown_directive_key_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            ConfigurationLoader.merge_configs(
                {"exclude+": ["a"]},  # missing the trailing 's'
                known_keys={"excludes"},
            )

        assert any("exclude+" in rec.message for rec in caplog.records)

    def test_known_directive_key_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            ConfigurationLoader.merge_configs(
                {"excludes+": ["a"]},
                known_keys={"excludes"},
            )

        assert not any("directive" in rec.message for rec in caplog.records)

    def test_no_known_keys_stays_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            ConfigurationLoader.merge_configs({"exclude+": ["a"]})

        assert not any("directive" in rec.message for rec in caplog.records)
