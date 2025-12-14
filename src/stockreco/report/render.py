from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def write_markdown(path: Path, target_date: str, as_of: str, agent_out: dict, scored_top: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    analyst = agent_out.get("analyst", {})
    final = analyst.get("final", [])
    notes = analyst.get("regime_notes", [])

    lines = []
    lines.append(f"# stockreco report — target date {target_date}")
    lines.append("")
    lines.append(f"- As-of EOD used: **{as_of}**")
    lines.append(f"- Final picks: **{len(final)}**")
    lines.append("")

    if notes:
        lines.append("## Notes")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## Final bullish momentum list (next day)")
    if not final:
        lines.append("_NO-TRADE: No high-conviction options trades for the next session (per rules)._")
        lines.append("")
    else:
        for i, item in enumerate(final, start=1):
            lines.append(f"### {i}) {item['ticker']}")
            lines.append(f"- Calibrated P(up tomorrow): **{item['p_up']:.2f}** ({item['confidence_label']})")
            # show Model-B if present
            if "p_expand" in item:
                lines.append(f"- Model-B P(expand ≥ thr): **{float(item['p_expand']):.2f}**")
            lines.append(f"- Rationale: {item['why']}")
            lines.append("- Options playbook:")
            for b in item.get("options_playbook", []):
                lines.append(f"  - {b}")
            lines.append("")

    lines.append("## Top 15 by options suitability (for reference)")
    scored_top = scored_top.copy()
    if "options_score" not in scored_top.columns:
        scored_top["options_score"] = 0.0
    if "p_expand" not in scored_top.columns:
        scored_top["p_expand"] = 0.0

    cols = ["ticker", "p_up", "p_expand", "score", "options_score", "rel_strength_5d", "rsi_14", "adx_14", "atr_pct"]
    cols = [c for c in cols if c in scored_top.columns]

    show = scored_top.head(15)[cols].copy()
    lines.append("")
    lines.append(show.to_markdown(index=False))
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
