"""Lot label layouts.

A layout turns processed catalog rows into a PDF of labels. AuctionFix ships one example layout (Avery 5160); other
packages add their own by declaring an entry point in the "auctionfix.label_layouts" group that points at a
LabelLayout, e.g. in their pyproject.toml:

    [project.entry-points."auctionfix.label_layouts"]
    house = "my_site.labels:HOUSE_LAYOUT"
"""
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

ENTRY_POINT_GROUP = "auctionfix.label_layouts"


@dataclass(frozen=True)
class LabelOptions:
    label_footer: str = ""
    # "" lets the layout use its own default
    company_name: str = ""
    auction_name: str = ""
    show_estimates: bool = True
    # draw each label's outline (for test prints)
    outline: bool = False
    # None: one label per item in the lot (its Qty), up to max_labels_per_lot; a number: that many per lot
    labels_per_lot: int | None = None
    max_labels_per_lot: int = 10


@dataclass(frozen=True)
class LabelLayout:
    key: str
    name: str
    # make(rows, output_path, options) writes the PDF and returns (label count, page count)
    make: Callable[[list[dict], Path, LabelOptions], tuple[int, int]]


def available_layouts() -> dict[str, LabelLayout]:
    """Built-in layouts plus any installed through the entry point group, keyed by LabelLayout.key."""
    from .avery5160 import AVERY_5160

    layouts = {AVERY_5160.key: AVERY_5160}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        layout = ep.load()
        layouts[layout.key] = layout
    return layouts


def make_labels(rows: list[dict], output_path: Path | str, layout: str = "avery5160",
                options: LabelOptions | None = None) -> tuple[int, int]:
    layouts = available_layouts()
    if layout not in layouts:
        raise ValueError(f"Unknown label layout {layout!r}; available: {', '.join(sorted(layouts))}")
    return layouts[layout].make(rows, Path(output_path), options or LabelOptions())
