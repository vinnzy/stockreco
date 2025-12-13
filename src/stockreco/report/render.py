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
        lines.append("_No picks passed reviewer filters._")
    else:
        for i, item in enumerate(final, start=1):
            lines.append(f"### {i}) {item['ticker']}")
            lines.append(f"- Calibrated P(up tomorrow): **{item['p_up']:.2f}** ({item['confidence_label']})")
            lines.append(f"- Rationale: {item['why']}")
            lines.append("- Options playbook:")
            for b in item.get("options_playbook", []):
                lines.append(f"  - {b}")
            lines.append("")

    lines.append("## Top 15 by model score (for reference)")
    show = scored_top.head(15)[["ticker","p_up","score","rel_strength_5d","rsi_14","adx_14","atr_pct"]].copy()
    lines.append("")
    lines.append(show.to_markdown(index=False))
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
