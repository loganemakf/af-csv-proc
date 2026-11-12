"""Example layout for Avery 5160 / 8160 address labels (1" x 2-5/8", 30 per Letter sheet)."""
from pathlib import Path

import labels
from reportlab.graphics import shapes
from reportlab.pdfbase.pdfmetrics import stringWidth

from .core import LabelLayout, LabelOptions
from .label_utils import label_copies, money

# Helvetica is built into every PDF reader and has the same character widths as Arial, so no font files are needed
FONT, BOLD = "Helvetica", "Helvetica-Bold"
WIDTH_PT = 2.625 * 72
MARGIN = 6
TITLE_SIZE = 9


def _wrap(text: str, width: float, lines: int) -> list[str]:
    """Up to `lines` lines that fit `width`; the last one ends in an ellipsis if the text doesn't fit."""
    words, out = text.split(), []
    while words and len(out) < lines:
        line = words.pop(0)
        while words and stringWidth(f"{line} {words[0]}", FONT, TITLE_SIZE) <= width:
            line += " " + words.pop(0)
        out.append(line)
    if words:
        last = out[-1]
        while last and stringWidth(last + "…", FONT, TITLE_SIZE) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + "…"
    return out


def _draw(label, width, height, row):
    # top: lot number, estimate on the right; then up to two title lines; bottom: company, auction and footer
    label.add(shapes.String(MARGIN, height - 17, "Lot", fontName=FONT, fontSize=9))
    label.add(shapes.String(MARGIN + 17, height - 17, row["LotNum"], fontName=BOLD, fontSize=14))
    if row.get("_estimate"):
        label.add(shapes.String(width - MARGIN, height - 16, row["_estimate"], fontName=FONT, fontSize=8,
                                textAnchor="end"))
    for i, line in enumerate(row["_title"]):
        label.add(shapes.String(MARGIN, height - 31 - i * 10.5, line, fontName=FONT, fontSize=TITLE_SIZE))
    footer = " \u00b7 ".join(t for t in (row.get("_company"), row.get("_auction"), row.get("_footer")) if t)
    if footer:
        label.add(shapes.String(width / 2, 6, footer, fontName=FONT, fontSize=6.5, textAnchor="middle"))


def prepare(rows: list[dict], options: LabelOptions) -> list[dict]:
    """One dict per label, with the text each part of the label shows."""
    prepared = []
    for row in label_copies(rows, options):
        lo, hi = money(row.get("LoEst")), money(row.get("HiEst"))
        row["_title"] = _wrap((row.get("Title") or "").strip(), WIDTH_PT - 2 * MARGIN, 2)
        # a lot without estimates gets no estimate line rather than "Est. $0 - $0"
        row["_estimate"] = f"Est. ${lo:,} - ${hi:,}" if options.show_estimates and (lo or hi) else ""
        row["_company"], row["_footer"], row["_auction"] = options.company_name, options.label_footer, options.auction_name
        prepared.append(row)
    return prepared


def make(rows: list[dict], output_path: Path, options: LabelOptions) -> tuple[int, int]:
    prepared = prepare(rows, options)
    # Letter page; 3 columns x 10 rows of 66.675 x 25.4 mm labels
    specs = labels.Specification(215.9, 279.4, 3, 10, 66.675, 25.4, corner_radius=2, column_gap=3.175,
                                 row_gap=0, top_margin=12.7, left_margin=4.7625)
    sheet = labels.Sheet(specs, _draw, border=options.outline)
    sheet.add_labels(prepared)
    sheet.save(str(output_path))
    return sheet.label_count, sheet.page_count


AVERY_5160 = LabelLayout("avery5160", "Avery 5160 (1\" x 2-5/8\")", make)
