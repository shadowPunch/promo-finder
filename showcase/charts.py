"""The two Altair charts on the Outputs page, styled to match the paper theme.
Colours were checked with the dataviz palette validator: red #B42318 and blue #1F63A8 pass on the paper surface."""
from __future__ import annotations

import altair as alt

INK, MUTED, RULE, RED, BLUE = "#1C1B19", "#6B6560", "#E4DED3", "#B42318", "#1F63A8"
FONT = "IBM Plex Sans, sans-serif"


def _style(chart: alt.Chart) -> alt.Chart:
    return (chart.configure(background="transparent", font=FONT)
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=MUTED, domainColor=RULE, tickColor=RULE, gridColor=RULE,
                            labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_legend(labelColor=INK, titleColor=MUTED, labelFontSize=12, orient="bottom", title=None))


def win_rates(rows: list[dict], highlight: str = "hook") -> alt.Chart:
    """Share of moments each re-cut type won, as thin horizontal bars; one type highlighted."""
    values = [{**r, "rate": r["won"] / r["tried"], "text": f"{r['won']} of {r['tried']}"} for r in rows]
    base = alt.Chart(alt.Data(values=values)).encode(
        y=alt.Y("label:N", sort=None, title=None, axis=alt.Axis(domain=False, ticks=False, labelPadding=8)))
    bars = base.mark_bar(height=14, cornerRadiusEnd=4).encode(
        x=alt.X("rate:Q", title=None, scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(format="%", grid=True, tickCount=4, domain=False)),
        color=alt.condition(f"datum.change == '{highlight}'", alt.value(RED), alt.value(MUTED)),
        tooltip=[alt.Tooltip("label:N", title="Cut"), alt.Tooltip("text:N", title="Moments won")])
    text = base.mark_text(align="left", dx=6, color=INK, fontSize=12).encode(x="rate:Q", text="text:N")
    return _style((bars + text).properties(height=34 * len(values)))


def still_watching(curve_a: list[float], curve_b: list[float]) -> alt.Chart:
    """Share of each simulated viewer still watching, second by second, with a hover crosshair."""
    values = [{"second": i, "share": s, "viewer": name}
              for name, curve in (("Core fan (A)", curve_a), ("Newcomer (B)", curve_b)) for i, s in enumerate(curve)]
    colour = alt.Color("viewer:N", scale=alt.Scale(domain=["Core fan (A)", "Newcomer (B)"], range=[RED, BLUE]))
    base = alt.Chart(alt.Data(values=values)).encode(
        x=alt.X("second:Q", title="seconds into the promo", axis=alt.Axis(grid=False, tickCount=6)),
        y=alt.Y("share:Q", title="still watching", scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(format="%", tickCount=4, domain=False)))
    hover = alt.selection_point(fields=["second"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    lines = base.mark_line(strokeWidth=2, interpolate="step-after").encode(color=colour)
    points = base.mark_point(size=60, filled=True, stroke="white", strokeWidth=2).encode(
        color=colour, opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("viewer:N", title="Viewer"), alt.Tooltip("second:Q", title="Second"),
                 alt.Tooltip("share:Q", title="Still watching", format=".0%")]).add_params(hover)
    rule = (alt.Chart(alt.Data(values=values)).mark_rule(color=MUTED, strokeDash=[3, 3])
            .encode(x="second:Q").transform_filter(hover))
    return _style((lines + rule + points).properties(height=190))
