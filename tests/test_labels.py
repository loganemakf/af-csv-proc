from auctionfix.cli import main
from auctionfix.labels import LabelOptions, available_layouts, make_labels
from auctionfix.labels.avery5160 import _wrap, prepare
from auctionfix.labels.label_utils import label_copies

ROWS = [
	{"LotNum": "12", "Title": "Federal Inlaid Mahogany Tall Case Clock With Painted Dial and Moon Phase", "Qty": "1",
	 "LoEst": "1500", "HiEst": "2500"},
	{"LotNum": "2A", "Title": "Pair of Brass Candlesticks", "Qty": "2", "LoEst": "0", "HiEst": "0"},
	{"LotNum": "3", "Title": "Box Lot", "Qty": "", "LoEst": "", "HiEst": ""},
]


def test_example_layout_is_built_in():
	assert "avery5160" in available_layouts()


def test_labels_per_item_in_lot_sorted_by_lot():
	assert [r["LotNum"] for r in label_copies(ROWS, LabelOptions())] == ["2A", "2A", "3", "12"]
	assert [r["LotNum"] for r in label_copies(ROWS, LabelOptions(labels_per_lot=1))] == ["2A", "3", "12"]
	assert len(label_copies([dict(ROWS[0], Qty="40")], LabelOptions())) == 10


def test_estimates_shown_by_default_and_never_as_zero(tmp_path):
	assert [r["_estimate"] for r in prepare(ROWS, LabelOptions(labels_per_lot=1))] == ["", "", "Est. $1,500 - $2,500"]
	assert {r["_estimate"] for r in prepare(ROWS, LabelOptions(show_estimates=False))} == {""}
	assert make_labels(ROWS, tmp_path / "labels.pdf") == (4, 1)
	assert (tmp_path / "labels.pdf").read_bytes().startswith(b"%PDF")


def test_long_titles_wrap_to_two_lines_with_ellipsis():
	lines = _wrap("Federal Inlaid Mahogany Tall Case Clock With Painted Dial, Moon Phase and Original Finial", 177, 2)
	assert len(lines) == 2 and lines[1].endswith("\u2026")


def test_cli_lists_layouts(capsys):
	assert main(["layouts"]) == 0
	assert "avery5160" in capsys.readouterr().out
