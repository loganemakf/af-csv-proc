import csv
import re
from collections import OrderedDict
import datetime
import copy
import os.path

from src import C
from src import try_pass

class CSVProc:

    def __init__(self):
        # keep track of issues with csv fields by lot number
        self.lot_warnings = {}

        # set of all possible supported columns in source catalog .csv file
        self.af_headers = {"LotNum", "Title", "Desc. 1", "Desc. 2", "Desc. 3", "Desc. 4", "Desc. 5", "LoEst",
                              "HiEst", "StartBid", "Condition", "Height", "Width", "Depth", "DimUnit", "Weight",
                              "WtUnit", "Reserve", "Qty", "Consign#", "Ref#", "[Ignore]", "[None]"}

        # dictionary mapping [af_headers]: [LiveAuctioneers headers]
        self.la_headers = {"LotNum": "LotNum", "Title": "Title", "Desc": "Description", "LoEst": "LowEst", "HiEst": "HiEst",
              "StartBid": "StartPrice", "Condition": "Condition", "BPCondition": "Condition", "Height": "Height",
              "Width": "Width", "Depth": "Depth", "DimUnit": "Dimension Unit", "Weight": "Weight", "WtUnit":
                  "Weight Unit", "Reserve": "Reserve Price", "Qty": "Quantity"}

        # dictionary mapping [af_headers]: [Invaluable headers]
        self.inv_headers = {"LotNum": "Lot Number", "LotExt": "Lot Ext", "Title": "Lot Title", "Desc": "Lot Description", "LoEst": "Lo Est",
                           "HiEst": "Hi Est", "StartBid": "Starting Bid", "Condition": "Condition"}

        self.data = []  # local copy of catalog file data

        self.file_headers = []  # subset of af_headers corresponding to columns in catalog .csv file
        self.export_file_headers = []
        self.src_path = ""      # the catalog .csv file
        self.dest_path = ""     # a folder to save exported LiveAuctioneers/Invaluable .csv  (and log) files in
        self.file_num_cols = 0

        # configuration options (user-configured in SettingsWindow)
        self.using_bp_condition = False
        self.bp_condition = ""  # text to substitute for every lot's "condition" field if using_bp_condition == True
        self.calc_startbid = False
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

        A source file must be defined before this method is called.

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


    def check_settings(self):
        """Checks whether current settings are valid (and sufficient).

        Returns: True if all checks pass, False otherwise.
        """
        # make sure number of headers provided matches number of cols in the file
        if len(self.file_headers) != self.file_num_cols:
            return False

        # if using boilerplate condition report, make sure there's text
        if self.using_bp_condition and len(self.bp_condition) <= 1:
            return False

        return True


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
            return True     # "warning" not found in list for "lot"
        except KeyError:
            return True     # no dictionary entry for "lot"

        return False    # "warning" already exists for "lot"


    def _load_af_csv(self):
        """Reads in data from an AuctionFlex-exported .csv file.

        Rows of the catalog .csv file specified by self.src_path are stored as dicts
        in self.data.
        """
        #TODO: probably check whether self.file_headers is empty (or the right length)
        with open(self.src_path, "r", encoding="latin-1", newline="") as af_file:
            self.data = []
            reader = csv.DictReader(af_file, fieldnames=self.file_headers)

            for line in reader:
                self.data.append(line)


    def _fix_descriptions(self):
        """Concatenates desc1-5 entries into a single dict entry, "Desc".
        """
        for record in self.data:
            try:
                record["Desc"] = record.pop("Desc. 1") + " " + record.pop("Desc. 2") + " " + record.pop("Desc. 3") + " " + \
                                 record.pop("Desc. 4") + " " + record.pop("Desc. 5")
            except KeyError:    # in case Condition is not defined
                pass

        self.export_file_headers = self.file_headers.copy()
        desc_index = self.export_file_headers.index("Desc. 1")
        self.export_file_headers.insert(desc_index, "Desc")

        for i in range(1, 6):
            self.export_file_headers.remove(f"Desc. {i}")


    def _process_conditions(self, data: list):
        """Handles condition truncation warning & boilerplate condition report substitution.
        """
        if self.using_bp_condition:
            for record in data:
                try:
                    record["Condition"] = self.bp_condition
                except KeyError:  # in case Condition is not defined
                    pass
        else:
            for record in data:
                self._log_error_if(len(record["Condition"]) == 221, record, "Condition has likely been cut off by "
                                                                            "AuctionFlex during export.")


    def _check_numeric_fields(self, data: list):
        """Checks parsibility of numeric fields.

        Integer fields checked: "Qty";
        Float fields checked: "LoEst", "HiEst", "StartBid", "Reserve"

        Args:
            data (list[dict]): A list of dicts representing csv file rows.

        Returns:
            bool: Whether all numeric fields are parsable as numbers.
        """
        all_numeric = True

        for record in data:
            try:
                float(record["Qty"])
            except ValueError:
                self._add_lot_warning(record["LotNum"], "Qty. field not parsable as an integer.")
                all_numeric = False
            except KeyError:    # in case Qty is not defined
                pass

            try:
                float(record["LoEst"])
                float(record["HiEst"])
                float(record["StartBid"])
            except ValueError:
                self._add_lot_warning(record["LotNum"], "Lo/HiEst or StartBid field not parsable as a number.")
                all_numeric = False
            except KeyError:    # in case StartBid is not defined
                pass

            try:
                float(record["Reserve"])
            except ValueError:
                self._add_lot_warning(record["LotNum"], "Reserve field not parsable as a number.")
                all_numeric = False
            except KeyError:    # in case Reserve is not defined
                pass

        return all_numeric


    def _uppercase_lotnums(self, data: list):
        for record in data:
            record["LotNum"] = record["LotNum"].upper().strip()


    def _process_startbids(self, data: list):
        for record in data:
            try:
                if self.calc_startbid:
                    if self.calc_empty_startbids:   # calculate empty startbid fields only
                        if not record["StartBid"] or float(record["StartBid"]) < 5.00:   # if startbid field is empty...
                            record["StartBid"] = 0.5 * float(record["LoEst"])
                    else:   # calculate all startbids
                        record["StartBid"] = 0.5 * float(record["LoEst"])
            except KeyError:    # in case StartBid is not defined
                pass


    def _format_whitespace(self, data: list):
        """Fixes whitespace irregularities in all records & fields of self.data.

        Replaces double+ spaces with single spaces and trims leading and trailing
        whitespace.
        """
        for record in data:
            for field in record:
                try:
                    record[field] = re.sub(' {2,}', ' ', record[field])
                    record[field] = record[field].strip()
                except TypeError:
                    pass    # handle (or rather, don't) empty fields


    def _find_errors(self, data: list):
        """Identifies obvious textual/formatting errors in the csv data.

        Checks for obvious signs that text data may be erroneously formatted.
        Warnings are generated here in the hope that they'll help identify
        more-serious errors present in lot data.

        Args:
            data (list[dict]): A list of dicts representing csv file rows.

        Raises:
            KeyError: If any of the keys used are not present in dicts of 'data'.
            ValueError: If float() fails.
        """
        for record in data:
            # if record["Desc"].find("  ") > -1:
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
            if float(record["LoEst"]) > float(record["HiEst"]):
                self._add_lot_warning(record["LotNum"], "Low estimate greater than high estimate.")
            if float(record["LoEst"]) < 5.00 or float(record["HiEst"]) < 5.00 or float(record["StartBid"]) < 5.00:
                self._add_lot_warning(record["LotNum"], "Lo/HiEst or StartBid is below $5.")

            self._log_error_if(not record["Condition"].isprintable(), record, "Condition contains unprintable "
                                                                           "characters).")
            self._log_error_if(not record["Condition"].isascii(), record, "Condition contains non-ASCII character(s).")
            self._log_error_if(not record["Condition"].endswith(('.', ')')), record, "Condition ends with a character other than '.' or ')'.")
            self._log_error_if(float(record["StartBid"]) > float(record["LoEst"]), record, "StartBid greater than low estimate.")
            self._log_error_if(float(record["StartBid"]) > float(record["HiEst"]), record, "StartBid greater than "
                                                                                           "high estimate.")


    @try_pass
    def _log_error_if(self, condition, curr_record, error_str):
        if condition:
            self._add_lot_warning(curr_record["LotNum"], error_str)


    @staticmethod
    def _is_float_str(s: str):
        #TODO: rewrite using regex
        for c in s:
            if not c.isdigit() and c != '.':
                return False

        return True


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
                #TODO: add support for "lot of #" and "# pieces"

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
        """Generates a logfile of lot warnings at location specified by 'path'.

        Exports the contents of lot_warnings to a text file.

        Raises:
            ?
        """
        # generate log file name
        fname = "Export_warnings_" + self._get_timestamp() + ".txt"
        path = os.path.join(self.dest_path, fname)

        warning_count = self.count_warnings()
        sorted_warnings = self._get_sorted_warnings()

        with open(path, "w") as log_file:
            log_file.write(80 * '#' + '\n')
            log_file.write(f"  {C.PROGRAM_NAME}  ".center(80) + '\n')
            log_file.write("   ~ Warnings ~   ".center(80) + '\n')
            log_file.write(f"   ({warning_count} issues found)   ".center(80) + '\n')
            log_file.write(80 * '#' + '\n\n')

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
        """Sorts lot numbers by value, accounting for alpha-extensions (ex. lot 205A)

        Args:
            s: lot_warnings dictionary tuple

        Returns:
            float: value used to index sort
        """
        if s[0].isnumeric():
            return float(s[0])
        elif re.search("[a-z]$", s[0], re.IGNORECASE):
            numeric_part = float(s[0][:-1])
            letter_part = float(ord(s[0][-1].upper())) / 100.0
            return numeric_part + letter_part
        else:
            return -1


    def count_warnings(self) -> int:
        """Counts the total number of warnings issued (for all lots).

        Returns:
            int: The total number of warnings in lot_warnings.
        """
        warning_count = 0
        for lot in self.lot_warnings:
            for _ in self.lot_warnings[lot]:
                warning_count += 1

        return warning_count


    def _split_lot_ext(self, data: list):
        """Separates numeric and alpha lot components.

        Adds a new "LotExt" entry to each dict in csv_data containing
        the alpha portion of "lot" (eg. LotNum=205A becomes LotNum=205 and LotExt=A).

        Args:
            data (list[dict]): A list of dicts representing csv file rows.

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
                    raise ValueError("Unexpected alpha character(s) in lot number.")


    def _export_invaluable(self, data: list, progress_callback, error_callback):
        # generate file name
        fname = "Invalu_Export_" + self._get_timestamp() + ".csv"
        path = os.path.join(self.dest_path, fname)

        # do the processing
        self._uppercase_lotnums(data)
        progress_callback(8)
        if self._check_numeric_fields(data):
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
            # self._check_title_quantities(data)

            # create header row (for ordering purposes)
            inv_headers = []
            for h in self.export_file_headers:
                try:
                    inv_headers.append(self.inv_headers[h])
                except KeyError:
                    pass

            progress_callback(29)
            # insert column for lot alpha-extensions
            lot_num_index = inv_headers.index("Lot Number")
            inv_headers.insert(lot_num_index + 1, "Lot Ext")

            with open(path, "w", newline="") as inv_file:
                writer = csv.DictWriter(inv_file, inv_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to Invaluable header keys
                    new_line = {}
                    for key, val in line.items():
                        try:
                            new_line[self.inv_headers[key]] = val
                        except KeyError:
                            pass

                    writer.writerow(new_line)

            print("Invaluable export complete")
        else:
            error_callback("Non-numeric value encountered in a numeric field; export aborted.")


    def _export_liveauctioneers(self, data: list, progress_callback, error_callback):
        # generate file name
        fname = "LiveAuc_Export_" + self._get_timestamp() + ".csv"
        path = os.path.join(self.dest_path, fname)

        # do the processing
        self._uppercase_lotnums(data)
        progress_callback(48)
        if self._check_numeric_fields(data):
            progress_callback(51)
            self._process_conditions(data)
            progress_callback(54)
            self._process_startbids(data)
            progress_callback(57)
            self._format_whitespace(data)
            progress_callback(60)
            self._find_errors(data)
            progress_callback(63)
            # self._check_title_quantities(data)

            # create header row (for ordering purposes)
            la_headers = []
            for h in self.export_file_headers:
                try:
                    la_headers.append(self.la_headers[h])
                except KeyError:
                    pass

            progress_callback(66)

            with open(path, "w", newline="") as la_file:
                writer = csv.DictWriter(la_file, la_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to LA header keys
                    new_line = {}
                    for key, val in line.items():
                        try:
                            new_line[self.la_headers[key]] = val
                        except KeyError:
                            pass

                    writer.writerow(new_line)

                    # line = {self.la_headers[key]: val for key, val in line.items()}
                    # # print(line)
                    # writer.writerow(line)

            print("Live auctioneers export complete")
        else:
            error_callback("Non-numeric value encountered in a numeric field; export aborted.")


    @staticmethod
    def _get_timestamp():
        return datetime.datetime.now().strftime("%m_%d_%Y")


    def process(self, *, progress_callback, result_callback):
        self._load_af_csv()
        progress_callback(0.0)

        self._fix_descriptions()
        progress_callback(2.5)    # set progress bar to 5%

        inv_data = copy.deepcopy(self.data)
        la_data = copy.deepcopy(self.data)
        progress_callback(5)

        self._export_invaluable(inv_data, progress_callback, result_callback)
        progress_callback(45)
        self._export_liveauctioneers(la_data, progress_callback, result_callback)
        progress_callback(90)

        if self.count_warnings() > 0:
            self._generate_warning_log()
            num_warnings = self.count_warnings()
            result_callback(f"{num_warnings} warnings generated; check log file")

        progress_callback(99.99)
