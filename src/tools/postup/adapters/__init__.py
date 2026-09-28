"""Postup adapters: subprocess delegation (git, gh) and the Click CLI."""

from __future__ import annotations

from postup.adapters.claude import ClaudeAdapter, ClaudeError
from postup.adapters.gh import GhAdapter, GhError
from postup.adapters.gitrepo import GitError, GitRepoAdapter

__all__ = ["ClaudeAdapter", "ClaudeError", "GhAdapter", "GhError", "GitError", "GitRepoAdapter"]
