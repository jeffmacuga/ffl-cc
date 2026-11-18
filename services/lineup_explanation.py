"""Local, rule-based explanations for lineup optimizer results."""

import math


def _format_projection(value):
    try:
        projection = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(projection):
        return None
    return f"{projection:.2f}"


def explain_lineup(context):
    """Build a concise explanation using only supplied optimizer data."""
    projection_source = context.get("projection_source", "available")
    objective = context.get("optimizer_objective") or (
        "The optimizer aims to maximize the supplied projections while "
        "respecting lineup eligibility and lock constraints."
    )
    explanation = [
        objective,
        f"The projection source is {projection_source}. Projections are "
        "estimates, not guaranteed results.",
    ]

    projection_summary = context.get("projection_summary")
    if isinstance(projection_summary, dict):
        current = _format_projection(projection_summary.get("current"))
        optimized = _format_projection(projection_summary.get("optimized"))
        if current is not None and optimized is not None:
            difference = _format_projection(
                float(optimized) - float(current)
            )
            sign = "+" if float(optimized) >= float(current) else ""
            explanation.append(
                f"Available projections total {current} for the current "
                f"lineup and {optimized} for the optimized lineup "
                f"({sign}{difference} points)."
            )

    changes = context.get("suggested_changes") or []
    if changes:
        explanation.append("Suggested changes:")
        for change in changes:
            player = change.get("Player") or "Player"
            position = change.get("Position")
            label = f"- {player}"
            if position:
                label += f" ({position})"
            current = change.get("Current Assignment")
            suggested = change.get("Suggested Assignment")
            if current or suggested:
                label += (
                    f": {current or 'Unassigned'} -> "
                    f"{suggested or 'Unassigned'}"
                )
            projection = _format_projection(change.get("Projection"))
            if projection is not None:
                label += f"; projection {projection}"
            explanation.append(label + ".")
    else:
        explanation.append(
            "The optimized lineup has no suggested assignment changes."
        )

    uncertainties = context.get("uncertainties") or []
    if uncertainties:
        explanation.append("Uncertainty to review:")
        explanation.extend(f"- {item}" for item in uncertainties)
    else:
        explanation.append(
            "No missing or zero projections were reported for the optimized "
            "lineup. Projection accuracy and late injury/news changes can "
            "still affect actual results."
        )
    return "\n\n".join(explanation)
