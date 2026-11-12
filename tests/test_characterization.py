"""Characterization tests: processing real AuctionFlex exports must keep producing the recorded outputs.

The recorded catalogs are private, so they live outside the repo. Point AUCTIONFIX_GOLDEN_DIR at a folder holding
settings.json (the GUI's config.json) and one folder per catalog with input.xml, invaluable.csv,
liveauctioneers.csv and (if any) warnings.txt. Without it these tests are skipped.
"""
import json
import os
import re
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GOLDEN_DIR = Path(os.environ["AUCTIONFIX_GOLDEN_DIR"]) if os.getenv("AUCTIONFIX_GOLDEN_DIR") else None
CATALOGS = sorted(p for p in GOLDEN_DIR.iterdir() if (p / "input.xml").exists()) if GOLDEN_DIR else []

pytestmark = pytest.mark.skipif(not CATALOGS, reason="AUCTIONFIX_GOLDEN_DIR not set")


def run_xml(xml: Path, out: Path, settings: dict) -> dict[str, Path]:
	"""Process one XML export the way the processor's script does; returns {output kind: path}."""
	from auctionfix import CONF
	from auctionfix.processor.xml_proc import XMLProc

	proc = XMLProc()
	proc.src_path, proc.dest_path = xml, out
	proc.using_bp_condition = settings[CONF.USING_BP_COND]
	proc.bp_condition = settings[CONF.BP_COND]
	proc.calc_startbids = True
	proc.calc_empty_startbids = True
	proc.process(progress_callback=lambda *a: None, result_callback=lambda *a: None)

	def one(pattern):
		found = list(out.glob(pattern))
		return found[0] if found else None

	return {"invaluable.csv": one("XML_Invalu_Export_*.csv"), "liveauctioneers.csv": one("XML_LiveAuc_Export_*.csv"),
			"warnings.txt": one("Export_warnings_*.txt")}


def _without_timestamp(text: str) -> list[str]:
	# the warning log's header carries the time it was written, e.g. "21:58:38 - Tue November 10, 2026"
	return [line for line in text.splitlines() if not re.match(r"\d\d:\d\d:\d\d - ", line)]


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda p: p.name)
def test_xml_exports_unchanged(catalog, tmp_path):
	settings = json.loads((GOLDEN_DIR / "settings.json").read_text())
	# the warning log names the input file, so process it under the catalog's original name
	xml = tmp_path / f"{catalog.name}.xml"
	shutil.copyfile(catalog / "input.xml", xml)
	out = tmp_path / "out"
	out.mkdir()
	outputs = run_xml(xml, out, settings)

	for kind in ("invaluable.csv", "liveauctioneers.csv"):
		assert outputs[kind] is not None, f"no {kind} written"
		assert outputs[kind].read_bytes() == (catalog / kind).read_bytes(), kind

	expected_warnings = catalog / "warnings.txt"
	if expected_warnings.exists():
		assert outputs["warnings.txt"] is not None, "no warning log written"
		assert _without_timestamp(outputs["warnings.txt"].read_text()) == _without_timestamp(expected_warnings.read_text())
	else:
		assert outputs["warnings.txt"] is None
