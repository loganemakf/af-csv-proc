import logging
import re
from collections import OrderedDict
import datetime
import pathlib
import csv
from pathlib import Path
import copy

from .. import C

log = logging.getLogger(__name__)


class AFProcessor:
    af_headers = [
        "LotNum",
        "Title",
        "Desc. 1",
        "Desc. 2",
        "Desc. 3",
        "Desc. 4",
        "Desc. 5",
        "Qty",
        "LoEst",
        "HiEst",
        "StartBid",
        "Reserve",
        "Condition",
        "Consign#",
        "Ref#",
        "Height",
        "Width",
        "Depth",
        "DimUnit",
        "Weight",
        "WtUnit",
        "Inv#",
        "[Ignore]",
        "[None]",
    ]

    # dictionary mapping [af_headers]: [LiveAuctioneers headers]
    la_headers = {
        "LotNum": "LotNum",
        "Title": "Title",
        "Desc": "Description",
        "LoEst": "LowEst",
        "HiEst": "HighEst",
        "StartBid": "StartPrice",
        "Condition": "Condition",
        "BPCondition": "Condition",
        "Height": "Height",
        "Width": "Width",
        "Depth": "Depth",
        "DimUnit": "Dimension Unit",
        "Weight": "Weight",
        "WtUnit": "Weight Unit",
        "Reserve": "Reserve Price",
        "Qty": "Quantity",
    }
    required_headers_la = [
        "LotNum",
        "Title",
        "Desc",
        "LoEst",
        "HiEst",
        "StartBid",
    ]

    # dictionary mapping [af_headers]: [Invaluable headers]
    inv_headers = {
        "LotNum": "Lot Number",
        "LotExt": "Lot Ext",
        "Title": "Lot Title",
        "Desc": "Lot Description",
        "LoEst": "Lo Est",
        "HiEst": "Hi Est",
        "StartBid": "Starting Bid",
        "Condition": "Condition",
    }
    required_headers_inv = ["LotNum", "Title", "Desc"]

    def __init__(self):
        # keep track of issues with csv fields by lot number
        self.lot_warnings = {}
        self.data = []  # local copy of catalog data

        # set of all possible (supported) columns in source catalog .csv file
        self.export_file_headers = []  # defines export column order
        self.src_path = Path()  # the catalog .csv file
        self.dest_path = (
            Path()
        )  # a folder to save exported LiveAuctioneers/Invaluable .csv (and log) files in
        self.file_num_cols = 0

        # configuration options (user-configured in SettingsWindow)
        self.using_bp_condition = False
        self.bp_condition = ""  # text to substitute for every lot's "Condition" field if using_bp_condition == True
        self.calc_startbids = False
        self.calc_empty_startbids = False

    def load_proc_csv(self, path, headers=None):
        with open(path, "r", newline="") as proc_file:
            self.data = []
            reader = (
                csv.DictReader(proc_file, fieldnames=headers)
                if headers
                else csv.DictReader(proc_file)
            )

            if (
                len(reader.fieldnames) == 0
                or len(reader.fieldnames) != self.file_num_cols
            ):
                raise RuntimeError(
                    "Catalog load error: mismatch in header/column count."
                )

            self.data = [line for line in reader]

    def save_proc_csv(self, path):
        with open(path, "w", newline="") as proc_file:
            writer = csv.DictWriter(proc_file, fieldnames=self.export_file_headers)
            writer.writeheader()
            for line in self.data:
                writer.writerow(line)

    def _replace_descriptions(self, replacements: dict):
        # replacements should be a dict in the form LotNum: Desc
        for record in self.data:
            if record["LotNum"] in replacements.keys():
                record["Desc"] = replacements[record["LotNum"]]

    def _add_lot_warning(self, lot: str, warning: str):
        """Adds str param 'warning' to lot_warnings['lot'].

        Args:
            lot: Dict key of the lot to add a warning for.
            warning: Warning text to be displayed in logfile.
        """
        try:
            if self._warning_not_exists(lot, warning):
                self.lot_warnings[lot].append(warning)
        except KeyError:
            self.lot_warnings[lot] = [
                warning,
            ]

    def _log_error_if(self, condition, curr_record, error_str):
        if condition:
            self._add_lot_warning(curr_record["LotNum"], error_str)

    def _warning_not_exists(self, lot: str, warning: str):
        try:
            self.lot_warnings[lot].index(warning)
        except ValueError:
            return True  # "warning" not found in list for key "lot"
        except KeyError:
            return True  # no dictionary entry for key "lot"

        return False  # "warning" already exists for key "lot"

    def _check_required_columns(self, data: list, required_cols: list):
        """Verifies that each record in dict 'data' contains all the keys in list 'required_cols'.

        Args:
            data: A list of dicts representing csv file rows.
            required_cols: A list of dict keys (column headers) required for this data.

        Raises:
            RuntimeError: If a required header is missing from any lot.
        """
        for header in required_cols:
            for record in data:
                if header not in record.keys():
                    raise RuntimeError(
                        f"Required column '{header}' not found for lot {record.get('LotNum', '')}."
                    )

    def _split_lot_ext(self, data: list):
        """Separates numeric and alpha lot components.

        Adds a new "LotExt" entry to each dict in 'data' containing
        the alpha portion of "LotNum" (ex: LotNum=205A becomes LotNum=205 and LotExt=A).

        Args:
            data: A list of dicts representing csv file rows.

        Raises:
            ValueError: If a lot contains non-terminating alpha characters.
        """
        for record in data:
            lot_num = record["LotNum"]

            if lot_num.isdecimal():
                record["LotExt"] = ""
            else:
                if lot_num[:-1].isdecimal() and lot_num[-1:].isalpha():
                    record["LotExt"] = lot_num[-1:]
                    record["LotNum"] = lot_num[:-1]
                else:
                    self._add_lot_warning(
                        lot_num, "Lot number contains non-terminating A-Z character(s)."
                    )
                    raise ValueError("Unexpected alpha character(s) in lot number.")

    def _process_conditions(self, data: list):
        """Handles condition report truncation warning & boilerplate condition report substitution."""
        if self.using_bp_condition:
            for record in data:
                record["Condition"] = self.bp_condition
        elif "Condition" in data[0].keys():
            for record in data:
                self._log_error_if(
                    len(record["Condition"]) == 221,
                    record,
                    "Condition has likely been cut off by "
                    "AuctionFlex during export.",
                )

    @staticmethod
    def _uppercase_lotnums(data: list):
        for record in data:
            record["LotNum"] = record["LotNum"].upper().strip()

    def _check_numeric_fields(self, data: list):
        """Checks parsability of numeric fields by attempting conversion to float or int as appropriate.

        Float fields checked: "Qty", "LoEst", "HiEst", "StartBid", "Reserve".

        Args:
            data: A list of dicts representing csv file rows.

        Returns:
            bool: Whether all numeric fields are parsable as numbers.
        """
        all_numeric = True

        for record in data:
            if "Qty" in record.keys():
                try:
                    if record["Qty"].strip() == "":
                        record["Qty"] = 1
                    float(record["Qty"])
                except ValueError:
                    self._add_lot_warning(
                        record["LotNum"], "Qty. field not parsable as a number."
                    )
                    all_numeric = False

            try:
                float(record["LoEst"])
                float(record["HiEst"])
                float(record["StartBid"])
            except ValueError:
                self._add_lot_warning(
                    record["LotNum"],
                    "Lo/HiEst or StartBid field not parsable as a number.",
                )
                all_numeric = False
            except KeyError:  # in case StartBid is not defined
                pass

            if "Reserve" in record.keys():
                try:
                    float(record["Reserve"])
                except ValueError:
                    self._add_lot_warning(
                        record["LotNum"], "Reserve field not parsable as a number."
                    )
                    all_numeric = False

        return all_numeric

    def _check_dimension_fields(self, data: list):
        dimension_fields = [
            field
            for field in ("Height", "Width", "Depth", "Weight")
            if field in data[0].keys()
        ]
        if not dimension_fields:
            return

        for record in data:
            for field in dimension_fields:
                if re.search(r"[^0-9.]", record[field]):
                    self._add_lot_warning(
                        record["LotNum"],
                        f'Dimension field "{field}" contains non-numeric value ('
                        f'current value: "{record[field]}")',
                    )

    def _check_related_columns(self, data: list):
        """Checks that related columns exist and, when one of a pair is filled in, the other is as well.
        Logs warnings as appropriate.

        Args:
            data: A list of dicts representing csv file rows.
        """
        first_record = data[0]
        # if H, W, or D are defined, dimension unit should also be defined (and vice-versa)
        if any(
            [
                field
                for field in ("Height", "Width", "Depth")
                if field in first_record.keys()
            ]
        ):
            if "DimUnit" not in first_record.keys():
                self._add_lot_warning(
                    "0",
                    "H/W/D column(s) defined but co-requisite Dim[ension]Unit column is not.",
                )
            else:
                # check all records with H/W/D defined for blank DimUnit fields
                for record in data:
                    if (
                        any(
                            [
                                record[field]
                                for field in ("Height", "Width", "Depth")
                                if field in record.keys()
                            ]
                        )
                        and not record["DimUnit"]
                    ):
                        self._add_lot_warning(
                            record["LotNum"], "Missing dimension unit."
                        )
        elif "DimUnit" in first_record.keys():
            if not any(
                [
                    field
                    for field in ("Height", "Width", "Depth")
                    if field in first_record.keys()
                ]
            ):
                self._add_lot_warning(
                    "0",
                    "DimUnit column defined but co-requisite H/W/D column(s) are not.",
                )

        # if Weight is defined, weight unit should be as well (and vice versa)
        if "Weight" in first_record.keys():
            if "WtUnit" not in first_record.keys():
                self._add_lot_warning(
                    "0",
                    "Weight column defined but co-requisite W[eigh]tUnit column is not.",
                )
            else:
                # check all records with Weight defined for blank WtUnit fields
                for record in data:
                    if record["Weight"] and not record["WtUnit"]:
                        self._add_lot_warning(record["LotNum"], "Missing weight unit.")
        elif "WtUnit" in first_record.keys():
            if "Weight" not in first_record.keys():
                self._add_lot_warning(
                    "0", "WtUnit column defined but co-requisite Weight column is not."
                )

        # if Consignor is defined, Ref# should be as well (and vice versa)
        if "Consign#" in first_record.keys():
            if "Ref#" not in first_record.keys():
                self._add_lot_warning(
                    "0", "Consign# column defined but co-requisite Ref# column is not."
                )
            # else:
            #     # todo: make this check a user-configurable setting
            #     # check all records with Consign# defined for blank Ref# fields
            #     for record in data:
            #         if record["Consign#"] and not record["Ref#"]:
            #             self._add_lot_warning(
            #                 record["LotNum"], "Missing consignor lot reference number."
            #             )
        elif "Ref#" in first_record.keys():
            if "Consign#" not in first_record.keys():
                self._add_lot_warning(
                    "0", "Ref# column defined but co-requisite Consign# column is not."
                )

    @staticmethod
    def _convert_numeric_to_int(data: list):
        # determine which numeric fields are present in 'data'
        integer_fields = ["LoEst", "HiEst", "StartBid", "Qty"]
        for field in integer_fields:
            if field not in data[0].keys():
                integer_fields.remove(field)

        # convert numeric fields from strings to integers
        for record in data:
            for field in integer_fields:
                record[field] = int(float(record[field]))

    def _process_startbids(self, data: list):
        """Calculates StartBids according to settings set by user."""
        for record in data:
            if self.calc_startbids:
                # calculate empty StartBid fields only
                if self.calc_empty_startbids and "StartBid" in record.keys():
                    if (
                        not record["StartBid"] or float(record["StartBid"]) < 5.00
                    ):  # if StartBid field is empty...
                        record["StartBid"] = 0.5 * float(record["LoEst"])
                elif "LoEst" in record.keys():  # calculate all StartBids
                    record["StartBid"] = 0.5 * float(record["LoEst"])

            if "Reserve" in record.keys():
                if "StartBid" in record.keys():
                    record["StartBid"] = max(
                        float(record["StartBid"]), float(record["Reserve"])
                    )
                else:
                    record["StartBid"] = record["Reserve"]

    @staticmethod
    def _format_whitespace(data: list):
        """Fixes whitespace irregularities in all records & fields of param 'data'.

        Replaces double+ spaces with single spaces and trims leading and trailing
        whitespace.
        """
        for record in data:
            for field in record:
                try:
                    record[field] = re.sub(" {2,}", " ", record[field])
                    record[field] = record[field].strip()
                except TypeError:
                    pass  # handle (or rather, don't handle) empty fields

    @staticmethod
    def _fix_unsupported_chars(data: list):
        text_fields = {"Title", "Desc", "Condition", "BPCondition"}

        for record in data:
            for key in text_fields & record.keys():
                record[key].encode("ascii", "ignore")

    def _fix_empty_descriptions(self, data: list):
        """Automatically fill empty descriptions with title and dimensions (if available)"""
        for record in data:
            if len(record["Desc"]) > 0:
                continue
            record["Desc"] = record["Title"]
            dimension_fields = {"Height", "Width", "Depth"}.intersection(
                self.export_file_headers
            )
            dimensions = ""
            if "DimUnit" not in self.export_file_headers:
                continue
            if "Height" in dimension_fields and record["Height"] is not None:
                dimensions += f"H: {record['Height']} {record['DimUnit']}."
            if "Width" in dimension_fields and record["Width"] is not None:
                dimensions += f"W: {record['Width']} {record['DimUnit']}."
            if "Depth" in dimension_fields and record["Depth"] is not None:
                dimensions += f"D: {record['Depth']} {record['DimUnit']}."
            record["Desc"] += f"\n\n{dimensions}"

            log.info("Empty description fixed for lot %s", record["LotNum"])

    @staticmethod
    def _fix_spaced_hyphenation(data: list):
        for record in data:
            original_desc = record["Desc"]
            record["Desc"] = re.sub(r"(\d+-)\s+(in[\w\.]+)", r"\1\2", record["Desc"])
            if record["Desc"] != original_desc:
                log.info("Removed spaced hyphenation from lot %s", record["LotNum"])
            erroneous_replacement = re.search(r"\d-in[^c.\s]", record["Desc"])
            if erroneous_replacement:
                log.warning("Erroneously de-hyphenated: %s", erroneous_replacement.group())

    # this is in-progress/experimental... might finish it later
    def _check_title_quantities(self, data: list):
        """Attempts to check whether quantity in lot title matches value in the "Qty" field.

        Args:
            data (list[dict]): A list of dicts representing csv file rows.
        """
        eng_qtys = re.compile(
            r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
            re.IGNORECASE,
        )
        eng_ints = {
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        for record in data:
            try:
                # look for spelled-out quantities
                if (
                    re.search("^pair", record["Title"], re.IGNORECASE)
                    and record["Qty"] != "2"
                ):
                    self._add_lot_warning(
                        record["LotNum"], "Title contains 'pair' but qty. is not 2."
                    )
                # TODO: add support for "lot of #" and "# pieces"

                # sum numeric quantities in title
                title_qtys = re.findall(r"\(\d+\)", record["Title"])
                total_qty = 0
                for q in title_qtys:
                    total_qty += int(q)

                # sum english quantities in title
                title_eng_qtys = eng_qtys.findall(record["Title"])
                for q in title_eng_qtys:
                    total_qty += eng_ints[q]

                if total_qty != float(record["Qty"]):
                    self._add_lot_warning(
                        record["LotNum"], "Possible mismatch between title & quantity."
                    )
            except KeyError:  # in case Qty is not defined
                pass

    def get_titles_for_lots_with_warnings(self):
        return {
            lot: record["Title"]
            for lot in self.lot_warnings
            for record in self.data
            if record["LotNum"].strip() == lot
        }

    def _generate_warning_log(self):
        """Generates a logfile of lot warnings at location specified by self.dest_path.

        Exports the contents of lot_warnings to a text file.
        """
        filename = "Export_warnings_" + self._get_timestamp() + ".txt"
        path = self.dest_path / filename

        warning_count = self.count_warnings()
        sorted_warnings = self._get_sorted_warnings()

        with open(path, "w") as log_file:
            source_filename = Path(self.src_path).name
            log_file.write(80 * "#" + "\n")
            log_file.write(f"{C.PROGRAM_NAME}".center(80) + "\n")
            log_file.write("~ Warnings ~".center(80) + "\n")
            log_file.write(
                f"({warning_count} potential issues identified)".center(80) + "\n"
            )
            log_file.write(f"Input file: {source_filename}".center(80) + "\n")
            log_file.write(80 * "#" + "\n\n")

            timestamp = datetime.datetime.now().strftime("%H:%M:%S - %a %B %d, %Y")
            log_file.write(f"{timestamp}\n\n")

            for lot in sorted_warnings:
                log_file.write(f"Lot {lot}  ".ljust(80, "-") + "\n")
                for warning in sorted_warnings[lot]:
                    log_file.write("   > " + warning + "\n")

                log_file.write("\n")

    def _get_sorted_warnings(self) -> OrderedDict:
        return OrderedDict(
            sorted(self.lot_warnings.items(), key=self._sort_value_with_alpha)
        )

    @staticmethod
    def _sort_value_with_alpha(s) -> float:
        """Sorts lot numbers by value (ascending), accounting for alpha-extensions (ex. lot 205A)

        Args:
            s: lot_warnings dictionary tuple

        Returns:
            float: value used to index sort
        """
        dict_key = s[0]
        if dict_key.isnumeric():
            return float(dict_key)
        elif re.search("[a-z]$", dict_key, re.IGNORECASE):
            numeric_part = float(dict_key[:-1])
            letter_part = float(ord(dict_key[-1].upper())) / 100.0
            return numeric_part + letter_part
        else:
            return -1

    def count_warnings(self) -> int:
        """Counts and returns the total number of warnings issued (for all lots)."""
        warning_count = 0
        for lot in self.lot_warnings:
            warning_count += len(self.lot_warnings[lot])

        return warning_count

    def _add_missing_export_headers(self, data: list):
        dict_headers = data[0].keys()

        for header in dict_headers:
            if header not in self.export_file_headers:
                if header == "LotExt":
                    # insert header column for lot alpha-extensions immediately after LotNum column
                    lot_num_index = self.export_file_headers.index("LotNum")
                    self.export_file_headers.insert(lot_num_index + 1, header)
                elif header == "StartBid":
                    lot_num_index = self.export_file_headers.index("HiEst")
                    self.export_file_headers.insert(lot_num_index + 1, header)
                else:
                    self.export_file_headers.append(header)

    @staticmethod
    def _get_timestamp():
        return datetime.datetime.now().strftime("%m_%d_%Y_%H%M%S")
