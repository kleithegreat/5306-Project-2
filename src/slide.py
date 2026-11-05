"""The one-slide summary, in the layout of Project 1's slide. Numbers from out/results.json.

    python src/slide.py   ->  slide/CS5306_Project2_Slide.pptx
"""

import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

INK, MUTED, CARD = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x52, 0x51, 0x4E), RGBColor(0xEE, 0xEC, 0xE6)
BLUE, ORANGE, AQUA = RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xEB, 0x68, 0x34), RGBColor(0x1B, 0xAF, 0x7A)
NAMES = {"CA": "California", "WA": "Washington", "NY": "New York", "TX": "Texas", "pooled": "All four"}


def text(slide, x, y, w, h, s, size, bold=False, color=INK, font=None):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    run = tf.paragraphs[0].add_run()
    run.text = s
    run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    if font:
        run.font.name = font
    return box


def card(slide, x, y, value, caption):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(2.15), Inches(1.1))
    shape.adjustments[0] = 0.07
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD
    shape.line.fill.background()
    text(slide, x + 0.2, y + 0.1, 1.9, 0.6, value, 21, bold=True, font="Cambria")
    text(slide, x + 0.2, y + 0.66, 1.8, 0.4, caption, 11, color=MUTED)


def main():
    r = json.load(open("out/results.json"))
    main_ = r["main"]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(10), Inches(5.625)
    s = prs.slides.add_slide(prs.slide_layouts[6])

    text(s, 0.5, 0.28, 9, 0.3, "CS 5306 / INFO 5306 Project 2  ·  Kevin Lei, Kyungmin Nam, Brittany Sun", 11, color=MUTED)
    text(s, 0.5, 0.58, 9, 0.95, "Do Google searches and Reddit posts improve nowcasts of state unemployment claims?", 26, bold=True)

    text(s, 0.5, 1.72, 4.5, 0.25, "THE QUESTION", 11, bold=True, color=MUTED)
    text(s, 0.5, 1.98, 4.5, 0.95,
         "Weekly claims are published five days late; searches and posts exist by Sunday. Do they beat "
         "past claims and the calendar, on weeks the models never saw (CA, WA, NY, TX, Oct 2023 \u2013 Sep 2026)?", 13)
    text(s, 0.5, 3.0, 4.5, 0.25, "THE ANSWER", 11, bold=True, color=MUTED)
    text(s, 0.5, 3.26, 4.5, 0.5,
         "Searches help, mostly in shock weeks. Reddit barely helps; tech-career posts help nowhere.", 13)

    trends, beryl = main_["pooled"]["trends"], r["where_gain"]["hurricane_beryl"]
    card(s, 0.5, 3.9, f"\u2212{trends['error_reduction_pct']}%", "squared nowcast error, adding Google searches")
    card(s, 2.85, 3.9, f"{beryl['baseline_error_pct']} \u2192 {beryl['trends_error_pct']}",
         "miss (log pts), Hurricane Beryl week, Texas")

    scopes = ["CA", "WA", "NY", "TX"]
    data = CategoryChartData()
    data.categories = [NAMES[st] for st in scopes]
    for model, label in (("trends", "+ Google searches"), ("reddit", "+ r/Unemployment"), ("tech", "+ r/cscareerquestions")):
        data.add_series(label, [main_[st][model]["error_reduction_pct"] for st in scopes])
    frame = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.4), Inches(1.72), Inches(4.2), Inches(3.3), data)
    chart = frame.chart
    chart.has_title = True
    chart.chart_title.text_frame.text = "Reduction in squared nowcast error vs. baseline (%), Oct 2023 \u2013 Sep 2026"
    chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(10)
    chart.value_axis.has_major_gridlines = False
    chart.value_axis.tick_labels.font.size = Pt(9)
    chart.category_axis.tick_labels.font.size = Pt(10)
    chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    for series, color in zip(chart.plots[0].series, (BLUE, ORANGE, AQUA)):
        series.invert_if_negative = False
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = color
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '0.0;\u22120.0'
    plot.data_labels.number_format_is_linked = False
    plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    plot.data_labels.font.size = Pt(9)

    Path("slide").mkdir(exist_ok=True)
    prs.save("slide/CS5306_Project2_Slide.pptx")


if __name__ == "__main__":
    main()
