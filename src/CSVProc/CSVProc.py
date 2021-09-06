# CSVProc.py
# af-csv-proc - Post-processor for exported auction catalogs
# Copyright (C) 2021  Logan Foster
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import csv
import re
from collections import OrderedDict
import datetime
import copy
import os.path
from src import C


class CSVProc:

    def __init__(self):
        # keep track of issues with csv fields by lot number
        self.lot_warnings = {}

        # set of all possible (supported) columns in source catalog .csv file
        self.af_headers = {"LotNum", "Title", "Desc. 1", "Desc. 2", "Desc. 3", "Desc. 4", "Desc. 5", "LoEst",
                              "HiEst", "StartBid", "Condition", "Height", "Width", "Depth", "DimUnit", "Weight",
                              "WtUnit", "Reserve", "Qty", "Consign#", "Ref#", "[Ignore]", "[None]"}

        # dictionary mapping [af_headers]: [LiveAuctioneers headers]
        self.la_headers = {"LotNum": "LotNum", "Title": "Title", "Desc": "Description", "LoEst": "LowEst",
                           "HiEst": "HighEst", "StartBid": "StartPrice", "Condition": "Condition", "BPCondition":
                               "Condition", "Height": "Height", "Width": "Width", "Depth": "Depth", "DimUnit":
                               "Dimension Unit", "Weight": "Weight", "WtUnit": "Weight Unit",
                           "Reserve": "Reserve Price", "Qty": "Quantity"}
        self.required_headers_la = ["LotNum", "Title", "Desc", "LoEst", "HiEst", "StartBid"]

        # dictionary mapping [af_headers]: [Invaluable headers]
        self.inv_headers = {"LotNum": "Lot Number", "LotExt": "Lot Ext", "Title": "Lot Title",
                            "Desc": "Lot Description", "LoEst": "Lo Est", "HiEst": "Hi Est",
                            "StartBid": "Starting Bid", "Condition": "Condition"}
        self.required_headers_inv = ["LotNum", "Title", "Desc"]

        self.data = []  # local copy of catalog data

        self.file_headers = []  # subset of af_headers corresponding to columns in catalog .csv file
        self.export_file_headers = []   # defines export column order
        self.src_path = ""      # the catalog .csv file
        self.dest_path = ""     # a folder to save exported LiveAuctioneers/Invaluable .csv (and log) files in
        self.file_num_cols = 0

        # configuration options (user-configured in SettingsWindow)
        self.using_bp_condition = False
        self.bp_condition = ""  # text to substitute for every lot's "Condition" field if using_bp_condition == True
        self.calc_startbids = False
        self.calc_empty_startbids = False



    @staticmethod
    def test_open(src_path: str):
        """Attempts to open param 'src_path' file for reading.

        Args:
            src_path: path to a readable file (likely .csv).

        Returns:
            bool: True if file can be opened, False if open() raises an OSError.
        """
        try:
            open(src_path)
            return True
        except OSError:
            return False


    def get_n_rows(self, n: int):
        """Returns first n-rows of source file (as a list of lists).

        self.src_path must be defined before this method is called.

        Args:
            n: The number of rows to read & return.

        Returns:
            list: The first n rows (as lists of strings) of the source file.

        Raises:
            RuntimeError: If no source file has been defined.

        Side effects:
            Sets self.file_num_cols to the number of columns in the first row
            read from the file at self.src_path.
        """
        if not self.src_path:
            raise RuntimeError("CSVProc error: no source file defined.")

        first_n_rows = []

        with open(self.src_path, "r", encoding="latin-1", newline="") as src_file:
            reader = csv.reader(src_file)

            line_counter = 0
            for line in reader:
                line_counter += 1
                if line_counter == 1:
                    self.file_num_cols = len(line)
                if line_counter <= n:
                    first_n_rows.append(line)
                else:
                    break

        return first_n_rows


    def set_file_col_headers(self, headers: list):
        if len(headers) == self.file_num_cols:
            self.file_headers = headers
        else:
            raise RuntimeError(f"Mismatched header/column count ({len(headers)} vs. {self.file_num_cols}).")


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
            self.lot_warnings[lot] = [warning,]


    def _warning_not_exists(self, lot: str, warning: str):
        try:
            self.lot_warnings[lot].index(warning)
        except ValueError:
            return True     # "warning" not found in list for key "lot"
        except KeyError:
            return True     # no dictionary entry for key "lot"

        return False    # "warning" already exists for key "lot"


    def _load_af_csv(self):
        """Reads in data from an AuctionFlex-exported .csv catalog file.

        Rows of the catalog file specified by self.src_path are stored as dicts in self.data.
        """
        if len(self.file_headers) == 0 or len(self.file_headers) != self.file_num_cols:
            raise RuntimeError("Catalog load error: mismatch in header/column count.")

        with open(self.src_path, "r", encoding="latin-1", newline="") as af_file:
            self.data = []
            reader = csv.DictReader(af_file, fieldnames=self.file_headers)

            self.data = [line for line in reader]


    def _fix_descriptions(self):
        """Concatenates 'Desc. [1-5]' entries into a single dict entry, "Desc".
        """
        for record in self.data:
            record["Desc"] = record.pop("Desc. 1") + " " + record.pop("Desc. 2") + " " + record.pop("Desc. 3") \
                             + " " + record.pop("Desc. 4") + " " + record.pop("Desc. 5")

        # insert new "Desc" header just before soon-to-be-removed "Desc. 1" header
        self.export_file_headers = self.file_headers.copy()
        desc_index = self.export_file_headers.index("Desc. 1")
        self.export_file_headers.insert(desc_index, "Desc")

        for i in range(1, 6):
            self.export_file_headers.remove(f"Desc. {i}")


    def _check_required_columns(self, data: list, required_cols: list):
        """Verifies that each record in dict 'data' contains all the keys in list 'required_cols'.
        A missing 'StartBid' column is ignored if the processor is set to calculate start bids
        (but not empty start bids).

        Args:
            data: A list of dicts representing csv file rows.
            required_cols: A list of dict keys (column headers) required for this data.

        Raises:
            RuntimeError: If a required header is missing from any lot.
        """
        for header in required_cols:
            for record in data:
                if header not in record.keys():
                    if not (header == "StartBid" and self.calc_startbids and not self.calc_empty_startbids):
                        raise RuntimeError(f"Required column '{header}' not found for lot.")


    def _process_conditions(self, data: list):
        """Handles condition report truncation warning & boilerplate condition report substitution.
        """
        if self.using_bp_condition:
            for record in data:
                record["Condition"] = self.bp_condition
        elif "Condition" in data[0].keys():
            for record in data:
                self._log_error_if(len(record["Condition"]) == 221, record, "Condition has likely been cut off by "
                                                                            "AuctionFlex during export.")


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
                    float(record["Qty"])
                except ValueError:
                    self._add_lot_warning(record["LotNum"], "Qty. field not parsable as a number.")
                    all_numeric = False

            try:
                float(record["LoEst"])
                float(record["HiEst"])
                float(record["StartBid"])
            except ValueError:
                self._add_lot_warning(record["LotNum"], "Lo/HiEst or StartBid field not parsable as a number.")
                all_numeric = False
            except KeyError:    # in case StartBid is not defined
                pass

            if "Reserve" in record.keys():
                try:
                    float(record["Reserve"])
                except ValueError:
                    self._add_lot_warning(record["LotNum"], "Reserve field not parsable as a number.")
                    all_numeric = False

        return all_numeric


    def _check_related_columns(self, data: list):
        """Checks that related columns exist and, when one of a pair is filled in, the other is as well.
        Logs warnings as appropriate.

        Args:
            data: A list of dicts representing csv file rows.
        """
        first_record = data[0]
        # if H, W, or D are defined, dimension unit should also be defined (and vice-versa)
        if any([field for field in ("Height", "Width", "Depth") if field in first_record.keys()]):
            if "DimUnit" not in first_record.keys():
                self._add_lot_warning("0", "H/W/D column(s) defined but co-requisite Dim[ension]Unit column is not.")
            else:
                # check all records with H/W/D defined for blank DimUnit fields
                for record in data:
                    if any([record[field] for field in ("Height", "Width", "Depth") if field in record.keys()]) and not record["DimUnit"]:
                        self._add_lot_warning(record["LotNum"], "Missing dimension unit.")
        elif "DimUnit" in first_record.keys():
            if not any([field for field in ("Height", "Width", "Depth") if field in first_record.keys()]):
                self._add_lot_warning("0", "DimUnit column defined but co-requisite H/W/D column(s) are not.")

        # if Weight is defined, weight unit should be as well (and vice-versa)
        if "Weight" in first_record.keys():
            if "WtUnit" not in first_record.keys():
                self._add_lot_warning("0", "Weight column defined but co-requisite W[eigh]tUnit column is not.")
            else:
                # check all records with Weight defined for blank WtUnit fields
                for record in data:
                    if record["Weight"] and not record["WtUnit"]:
                        self._add_lot_warning(record["LotNum"], "Missing weight unit.")
        elif "WtUnit" in first_record.keys():
            if "Weight" not in first_record.keys():
                self._add_lot_warning("0", "WtUnit column defined but co-requisite Weight column is not.")

        # if Consignor is defined, Ref# should be as well (and vice-versa)
        if "Consign#" in first_record.keys():
            if "Ref#" not in first_record.keys():
                self._add_lot_warning("0", "Consign# column defined but co-requisite Ref# column is not.")
            else:
                # check all records with Consign# defined for blank Ref# fields
                for record in data:
                    if record["Consign#"] and not record["Ref#"]:
                        self._add_lot_warning(record["LotNum"], "Missing consignor lot reference number.")
        elif "Ref#" in first_record.keys():
            if "Consign#" not in first_record.keys():
                self._add_lot_warning("0", "Ref# column defined but co-requisite Consign# column is not.")


    @staticmethod
    def _convert_numeric_to_int(data: list):
        # determine which numeric fields are present in 'data'
        integer_fields = ["LoEst", "HiEst", "StartBid"]
        present_int_fields = []
        for field in integer_fields:
            if field in data[0].keys():
                present_int_fields.append(field)

        # convert numeric fields from strings to integers
        for record in data:
            for field in present_int_fields:
                record[field] = int(float(record[field]))


    def _process_startbids(self, data: list):
        """Calculates StartBids according to settings set by user.
        """
        for record in data:
            if self.calc_startbids:
                # calculate empty StartBid fields only
                if self.calc_empty_startbids and "StartBid" in record.keys():
                    if not record["StartBid"] or float(record["StartBid"]) < 5.00:   # if StartBid field is empty...
                        record["StartBid"] = 0.5 * float(record["LoEst"])
                elif "LoEst" in record.keys():   # calculate all StartBids
                    record["StartBid"] = 0.5 * float(record["LoEst"])


    @staticmethod
    def _format_whitespace(data: list):
        """Fixes whitespace irregularities in all records & fields of param 'data'.

        Replaces double+ spaces with single spaces and trims leading and trailing
        whitespace.
        """
        for record in data:
            for field in record:
                try:
                    record[field] = re.sub(' {2,}', ' ', record[field])
                    record[field] = record[field].strip()
                except TypeError:
                    pass    # handle (or rather, don't handle) empty fields


    def _find_errors(self, data: list):
        """Identifies obvious textual/formatting errors in the catalog data.

        Checks for obvious signs that text data may be erroneously formatted.
        Warnings are generated here in the hope that they'll help the user identify
        more-serious errors present in lot data.

        Args:
            data: A list of dicts representing csv file rows.

        Raises:
            KeyError: If any required keys are not present in dicts of 'data'.
            ValueError: If float() fails (call this function after _check_numeric_fields() ).
        """
        for record in data:
            # checks for required fields
            if "  " in record["Desc"]:
                self._add_lot_warning(record["LotNum"], "Double space found.")
            if not record["Desc"].endswith(('.', ')')):
                self._add_lot_warning(record["LotNum"], "Description ends with a character other than '.' or ')'.")
            if not record["Desc"].isascii():
                self._add_lot_warning(record["LotNum"], "Description contains non-ASCII character(s).")
            if not record["Desc"].isprintable():
                self._add_lot_warning(record["LotNum"], "Description contains unprintable character(s).")
            if len(record["Title"]) > 60:
                self._add_lot_warning(record["LotNum"], "Title longer than 60 characters.")

            # checks for optional fields
            if "LoEst" in record.keys() and "HiEst" in record.keys():
                if float(record["LoEst"]) >= float(record["HiEst"]):
                    self._add_lot_warning(record["LotNum"], "Low estimate greater than or equal to high estimate.")
                if float(record["LoEst"]) < 10.00 or float(record["HiEst"]) < 10.00 or \
                        float(record.get("StartBid", float(record["LoEst"]) / 2.0)) < 5.00:
                    self._add_lot_warning(record["LotNum"], "Lo/HiEst is below $10 or StartBid is below $5.")

            if "Condition" in record.keys():
                self._log_error_if(not record["Condition"].isprintable(), record, "Condition contains unprintable "
                                                                               "character(s).")
                self._log_error_if(not record["Condition"].isascii(), record, "Condition contains non-ASCII character(s).")
                self._log_error_if(not record["Condition"].endswith(('.', ')')), record, "Condition ends with a character other than '.' or ')'.")

            if "StartBid" in record.keys():
                self._log_error_if(float(record["StartBid"]) > float(record["LoEst"]), record, "StartBid greater than low estimate.")
                self._log_error_if(float(record["StartBid"]) > float(record["HiEst"]), record, "StartBid greater than "
                                                                                           "high estimate.")


    def _log_error_if(self, condition, curr_record, error_str):
        if condition:
            self._add_lot_warning(curr_record["LotNum"], error_str)


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
                    self._add_lot_warning(lot_num, "Lot number contains non-terminating A-Z character(s).")
                    raise ValueError(f"Unexpected alpha character(s) in lot {lot_num}.")


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


    # this is in-progress/experimental... might finish it later
    def _check_title_quantities(self, data: list):
        """Attempts to check whether quantity in lot title matches value in the "Qty" field.

        Args:
            data (list[dict]): A list of dicts representing csv file rows.
        """
        eng_qtys = re.compile(r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b", re.IGNORECASE)
        eng_ints = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                    "ten": 10, "eleven": 11, "twelve": 12}

        for record in data:
            try:
                # look for spelled-out quantities
                if re.search("^pair", record["Title"], re.IGNORECASE) and record["Qty"] != "2":
                    self._add_lot_warning(record["LotNum"], "Title contains 'pair' but qty. is not 2.")
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
                    self._add_lot_warning(record["LotNum"], "Possible mismatch between title & quantity.")
            except KeyError:    # in case Qty is not defined
                pass


    def _generate_warning_log(self):
        """Generates a logfile of lot warnings at location specified by self.dest_path.

        Exports the contents of lot_warnings to a text file.
        """
        filename = "Export_warnings_" + self._get_timestamp() + ".txt"
        path = os.path.join(self.dest_path, filename)

        warning_count = self.count_warnings()
        sorted_warnings = self._get_sorted_warnings()

        with open(path, "w") as log_file:
            log_file.write(80*'#' + '\n')
            log_file.write(f"{C.PROGRAM_NAME}".center(80) + '\n')
            log_file.write("~ Warnings ~".center(80) + '\n')
            log_file.write(f"({warning_count} potential issues identified)".center(80) + '\n')
            log_file.write(80*'#' + '\n\n')

            timestamp = datetime.datetime.now().strftime("%H:%M:%S - %a %B %d, %Y")
            log_file.write(f"{timestamp}\n\n")

            for lot in sorted_warnings:
                log_file.write(f"Lot {lot}  ".ljust(80, '-') + '\n')
                for warning in sorted_warnings[lot]:
                    log_file.write('   > ' + warning + '\n')

                log_file.write('\n')


    def _get_sorted_warnings(self) -> OrderedDict:
        return OrderedDict(sorted(self.lot_warnings.items(), key=self._sort_value_with_alpha))


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
        """Counts and returns the total number of warnings issued (for all lots).
        """
        warning_count = 0
        for lot in self.lot_warnings:
            warning_count += len(self.lot_warnings[lot])

        return warning_count


    def _export_invaluable(self, data: list, progress_callback, error_callback):
        filename = "Invalu_Export_" + self._get_timestamp() + ".csv"
        path = os.path.join(self.dest_path, filename)

        # verify that required fields are all present
        try:
            self._check_required_columns(data, self.required_headers_inv)
        except RuntimeError as e:
            error_callback("Invaluable export error: " + str(e))
            raise e

        # process data for upload to Invaluable
        self._uppercase_lotnums(data)
        progress_callback(8)
        if self._check_numeric_fields(data):
            self._check_related_columns(data)
            progress_callback(11)
            self._process_conditions(data)
            progress_callback(14)
            self._process_startbids(data)
            progress_callback(17)
            self._format_whitespace(data)
            progress_callback(20)
            self._find_errors(data)
            progress_callback(23)
            self._split_lot_ext(data)
            progress_callback(26)
            self._convert_numeric_to_int(data)
            self._add_missing_export_headers(data)
            # self._check_title_quantities(data)

            # create header row (for ordering purposes)
            exp_headers = [self.inv_headers[h] for h in self.export_file_headers if h in self.inv_headers]
            progress_callback(29)

            with open(path, "w", newline="") as inv_file:
                writer = csv.DictWriter(inv_file, exp_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to Invaluable header keys
                    new_line = {self.inv_headers[key]: val for (key, val) in line.items() if key in
                                self.inv_headers.keys()}
                    writer.writerow(new_line)

        else:
            error_callback("Non-numeric value encountered in a numeric field; export aborted.")


    def _export_liveauctioneers(self, data: list, progress_callback, error_callback):
        filename = "LiveAuc_Export_" + self._get_timestamp() + ".csv"
        path = os.path.join(self.dest_path, filename)

        # verify that required fields are all present
        try:
            self._check_required_columns(data, self.required_headers_la)
        except RuntimeError as e:
            error_callback("LiveAuctioneers export error: " + str(e))
            raise e

        # process data for upload to LiveAuctioneers
        self._uppercase_lotnums(data)
        progress_callback(48)
        if self._check_numeric_fields(data):
            self._check_related_columns(data)
            progress_callback(51)
            self._process_conditions(data)
            progress_callback(54)
            self._process_startbids(data)
            progress_callback(57)
            self._format_whitespace(data)
            progress_callback(60)
            self._find_errors(data)
            self._add_missing_export_headers(data)
            progress_callback(63)
            # self._check_title_quantities(data)

            # create header row (for ordering purposes)
            exp_headers = [self.la_headers[h] for h in self.export_file_headers if h in self.la_headers]

            progress_callback(66)

            with open(path, "w", newline="") as la_file:
                writer = csv.DictWriter(la_file, exp_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to LA header keys
                    new_line = {self.la_headers[key]: val for (key, val) in line.items() if key in
                                self.la_headers.keys()}
                    writer.writerow(new_line)

        else:
            error_callback("Non-numeric value encountered in a numeric field; export aborted.")


    @staticmethod
    def _get_timestamp():
        return datetime.datetime.now().strftime("%m_%d_%Y")


    def process(self, *, progress_callback, result_callback):
        """Coordinates LA & Inv. catalog processing+export and warning log creation.

        Args:
            progress_callback: func. with int param for updating progressbar in MainWindow
            result_callback: func. with str param for displaying message to user after processing/export is done.
        """
        # load data from the catalog .csv file into self.data
        self._load_af_csv()
        progress_callback(0.0)

        self._fix_descriptions()
        progress_callback(2.5)    # set progress bar to 2.5%

        inv_data = copy.deepcopy(self.data)
        la_data = copy.deepcopy(self.data)
        progress_callback(5)

        try:
            # process and export the catalog for upload to both bidding platforms
            self._export_invaluable(inv_data, progress_callback, result_callback)
            progress_callback(45)
            self._export_liveauctioneers(la_data, progress_callback, result_callback)
            progress_callback(90)

            # generate warning log as necessary
            num_warnings = self.count_warnings()
            if num_warnings > 0:
                self._generate_warning_log()
                result_callback(f"{num_warnings} warnings generated; check log file")

            # setting progressbar value to 99+ makes it appear full (whereas 100 looks empty)
            progress_callback(99.99)
        except RuntimeError:
            progress_callback(0.0)
        except ValueError as e:
            result_callback(f"Export error: {e}")
