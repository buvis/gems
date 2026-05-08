from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.rules.extractor import apply_extract
from bim.commands.doc.shared.rules.matcher import evaluate_match
from bim.commands.doc.shared.rules.models import Rule, RuleResult, SourceMetadata

__all__ = [
    "RuleEngine",
]


@dataclass(frozen=True)
class _Survivor:
    rule: Rule
    owning_slug: str
    pinned: dict[str, object]
    definition_index: int


def _issuer_slug_values(survivors: list[_Survivor]) -> set[object]:
    return {survivor.pinned["issuer_slug"] for survivor in survivors if "issuer_slug" in survivor.pinned}


def _pick_result(kind: Literal["full", "partial"], survivors: list[_Survivor]) -> RuleResult:
    ordered = sorted(survivors, key=lambda survivor: (-survivor.rule.priority, survivor.definition_index))
    picked = ordered[0]
    top_group = [survivor for survivor in ordered if survivor.rule.priority == picked.rule.priority]

    if len(_issuer_slug_values(top_group)) > 1:
        return RuleResult(
            kind="conflict",
            rule_id=None,
            rule_version=None,
            conflicting_rules=[survivor.rule.id for survivor in top_group],
        )

    return RuleResult(
        kind=kind,
        rule_id=picked.rule.id,
        rule_version=picked.rule.version,
        pinned=picked.pinned,
    )


def _select_winner(survivors: list[_Survivor]) -> RuleResult:
    full = [survivor for survivor in survivors if not survivor.rule.partial]
    if full:
        return _pick_result("full", full)

    partial = [survivor for survivor in survivors if survivor.rule.partial]
    if partial:
        return _pick_result("partial", partial)

    return RuleResult(kind="none", rule_id=None, rule_version=None)


class RuleEngine:
    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        ocr_text: str,
        source: SourceMetadata,
        registry: IssuerRegistry,
        *,
        scoped_issuer_slug: str | None = None,
    ) -> RuleResult:
        survivors: list[_Survivor] = []
        definition_index = 0

        for owning_slug, entry in registry.issuers.items():
            if scoped_issuer_slug is not None and owning_slug != scoped_issuer_slug:
                continue
            for rule in entry.rules:
                if not rule.enabled:
                    continue
                match_result = evaluate_match(rule, ocr_text, source)
                if not match_result.matched:
                    continue
                pinned = apply_extract(rule, ocr_text, source, match_result.captures)
                if pinned is None:
                    continue
                survivors.append(
                    _Survivor(
                        rule=rule,
                        owning_slug=owning_slug,
                        pinned=pinned,
                        definition_index=definition_index,
                    )
                )
                definition_index += 1

        return _select_winner(survivors)
