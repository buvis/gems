"""Tests for the TUI RescueCollisionModal."""

from __future__ import annotations

from dot.tui.widgets.rescue_modal import RescueCollisionModal


class TestRescueCollisionModal:
    def test_modal_stores_target_and_source(self) -> None:
        modal = RescueCollisionModal(target=".vimrc", source=".local/.vimrc")

        assert modal._target == ".vimrc"
        assert modal._source == ".local/.vimrc"

    def test_has_expected_bindings(self) -> None:
        bindings = {b.key: b.action for b in RescueCollisionModal.BINDINGS}

        assert bindings["s"] == "keep_source"
        assert bindings["t"] == "keep_target"
        assert bindings["escape"] == "cancel"

    def test_action_keep_source_exists(self) -> None:
        modal = RescueCollisionModal(target=".vimrc", source=".local/.vimrc")

        # Verify the action method exists and can be called
        # (dismiss() will be called but requires app context in full tests)
        assert hasattr(modal, "action_keep_source")
        assert callable(modal.action_keep_source)

    def test_action_keep_target_exists(self) -> None:
        modal = RescueCollisionModal(target=".vimrc", source=".local/.vimrc")

        assert hasattr(modal, "action_keep_target")
        assert callable(modal.action_keep_target)

    def test_action_cancel_exists(self) -> None:
        modal = RescueCollisionModal(target=".vimrc", source=".local/.vimrc")

        assert hasattr(modal, "action_cancel")
        assert callable(modal.action_cancel)

    def test_is_modal_screen(self) -> None:
        from textual.screen import ModalScreen

        modal = RescueCollisionModal(target=".vimrc", source=".local/.vimrc")
        assert isinstance(modal, ModalScreen)
