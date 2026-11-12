from auctionfix.processor.csv_proc import CSVProc
from auctionfix.processor.xml_proc import XMLProc


def test_xml_and_csv_processors_keep_their_own_headers():
	assert [h for h in CSVProc.af_headers if h.startswith("Desc")] == [f"Desc. {i}" for i in range(1, 6)]
	assert XMLProc.af_headers[:3] == ["LotNum", "Title", "Desc"]
	assert not any(h.startswith("Desc. ") for h in XMLProc.af_headers)
	assert XMLProc.af_headers[3:] == [h for h in CSVProc.af_headers[2:] if not h.startswith("Desc. ")]
