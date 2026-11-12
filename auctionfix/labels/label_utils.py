import copy
import re


# Function used to sort lotnum's w/ possible alpha-suffixes
def sort_by_lotnum(item: dict):
	s = item["LotNum"]

	if s.isnumeric():
		return float(s)
	elif re.search("[a-z]$", s, re.IGNORECASE):
		numeric_part = float(s[:-1])
		letter_part = float(ord(s[-1].upper())) / 100.0
		return numeric_part + letter_part
	else:
		return -1


def label_copies(rows: list[dict], options) -> list[dict]:
	"""Rows repeated as many times as each lot needs labels, sorted by lot number."""
	out = []
	for row in rows:
		if options.labels_per_lot is not None:
			count = options.labels_per_lot
		else:
			count = min(max(int(float(row.get("Qty") or 0)), 1), options.max_labels_per_lot)
		out.extend(copy.copy(row) for _ in range(count))
	return sorted(out, key=sort_by_lotnum)


def money(value) -> int:
	try:
		return int(float(value or 0))
	except ValueError:
		return 0
