import json
import os
import shutil
from pathlib import Path

import pytest

from auctionfix.cli import main

GOLDEN_DIR = Path(os.environ["AUCTIONFIX_GOLDEN_DIR"]) if os.getenv("AUCTIONFIX_GOLDEN_DIR") else None


def test_csv_input_is_refused(tmp_path, capsys):
	assert main(["process", str(tmp_path / "catalog.csv")]) == 2
	assert "GUI" in capsys.readouterr().err


@pytest.mark.skipif(GOLDEN_DIR is None, reason="AUCTIONFIX_GOLDEN_DIR not set")
def test_process_matches_recorded_exports(tmp_path):
	catalog = sorted(p for p in GOLDEN_DIR.iterdir() if (p / "input.xml").exists())[0]
	xml = tmp_path / f"{catalog.name}.xml"
	shutil.copyfile(catalog / "input.xml", xml)
	assert main(["process", str(xml), "-o", str(tmp_path / "out"), "--settings", str(GOLDEN_DIR / "settings.json")]) == 0
	la = next((tmp_path / "out").glob("XML_LiveAuc_Export_*.csv"))
	assert la.read_bytes() == (catalog / "liveauctioneers.csv").read_bytes()
