# using google docstring conventions: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings

import csv
import re
import copy


class CSVProc:

    def __init__(self):
        # keep track of issues with csv fields by lot number
        self.lot_warnings = {}

        self.af_headers = {"LotNum", "Title", "Desc. 1", "Desc. 2", "Desc. 3", "Desc. 4", "Desc. 5", "LoEst",
                              "HiEst", "StartBid", "Condition", "Height", "Width", "Depth", "DimUnit", "Weight",
                              "WtUnit", "Reserve", "Qty", "[None]"}

        self.la_headers = {"LotNum": "LotNum", "Title": "Title", "Desc": "Description", "LoEst": "LowEst", "HiEst": "HiEst",
              "StartBid": "StartPrice", "Condition": "Condition", "BPCondition": "Condition", "Height": "Height",
              "Width": "Width", "Depth": "Depth", "DimUnit": "Dimension Unit", "Weight": "Weight", "WtUnit":
                  "Weight Unit", "Reserve": "Reserve Price", "Qty": "Quantity"}

        self.inv_headers = ["Lot Number", "Lot Ext", "Lot Title", "Lot Description", "Lo Est", "Hi Est", "Starting Bid", "Condition"]

        self.data = []

        self.file_headers = []
        self.src_path = ""
        self.dest_path = ""
        self.using_bp_condition = False
        self.bp_condition = ""
        self.file_num_cols = 0



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
            RuntimeError: If no source file is defined.

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
            raise RuntimeError(f"Mismatched header/column count ({len(headers)} vs {self.file_num_cols}).")


    # checks whether current settings are valid (and sufficient)
    def check_settings(self):
        # make sure number of headers provided matches number of cols in the file
        if len(self.file_headers) != self.file_num_cols:
            return False

        # if using boilerplate condition report, make sure there's text
        if self.using_bp_condition and len(self.bp_condition) <= 1:
            return False

        return True


    def _add_lot_warning(self, lot: str, warning: str):
        """Adds param 'warning' to lot_warnings[lot].

        Args:
            lot: Dict key of the lot to add a warning for.
            warning: Warning text to be displayed in logfile.

        Returns:
            None
        """
        try:
            self.lot_warnings[lot].append(warning)
        except KeyError:
            self.lot_warnings[lot] = [warning,]


    def load_af_csv(self, path: str, col_headers: list):
        """Reads in data from an AuctionFlex-exported .csv file.

        Rows of the .csv file specified by 'path' argument are stored as dicts
        in self.data list. The condition field is also checked for truncation
        and a warning is set if necessary.

        Args:
            path (str): The path to the csv file to open.
            col_headers (list[str]): A list of column headers for the file
                indicated by 'path'.

        Side effects:
            Sets value of file_num_cols to the number of columns in the first
                row of the CSV.
        """
        self.data = []

        with open(path, "r", encoding="latin-1", newline="") as af_file:
            reader = csv.DictReader(af_file, fieldnames=col_headers)

            execute_once = True

            for line in reader:
                self.data.append(line)

                # store the number of columns in the first row for later use
                if execute_once:
                    self.file_num_cols = len(line)
                    execute_once = False


    def count_warnings(self) -> int:
        """Counts the total number of warnings issued (for all lots).

        Args:
            None

        Returns:
            int: The total number of warnings in lot_warnings.
        """
        warning_count = 0
        for lot in self.lot_warnings:
            for _ in self.lot_warnings[lot]:
                warning_count += 1

        return warning_count


    def fix_descriptions(self):
        """Concatenates desc1-5 entries into a single dict entry, "desc".
        """

        for row in self.data:
            row["desc"] = row.pop("desc1") + " " + row.pop("desc2") + " " + row.pop("desc3") + " " + row.pop(
                "desc4") + " " + row.pop("desc5")

            # TODO: remove next line (suppresses 500+ warnings for unpunctuated conditions in test csv)
            row["condition"] += '.'


    # TODO: move conditionTruncated logic to load_af_csv or change its docstring
    def format_whitespace(self):
        """Fixes whitespace irregularities in all rows & fields of 'csv_data'.

        Replaces double spaces with single spaces and trims leading and trailing
        whitespace.

        Args:
            csv_data (list): A list of dicts representing csv file rows.

        Returns:
            list[dict]: 'csv_data', but with the aforementioned formatting applied.

        Raises:
            KeyError: If "lot" or "condition" keys are not present in 'csv_data'.
        """

        for csv_line in self.data:
            condition_truncated = True if len(csv_line["condition"]) == 221 else False

            for column in csv_line:
                # next line only worked for double spaces (not triple, etc.)
                # csv_line[column] = csv_line[column].replace("  ", " ")

                csv_line[column] = re.sub(' {2,}', ' ', csv_line[column])
                csv_line[column] = csv_line[column].strip()

            if condition_truncated:
                self._add_lot_warning(csv_line["lot"], "Condition has likely been cut off by AuctionFlex during "
                                                       "export.")


    def find_errors(self):
        """Identifies obvious textual/formatting errors in the csv data.

        Checks for obvious signs that text data may be erroneously formatted.
        Warnings are generated here in the hope that they'll help identify
        more-serious errors present in lot data.

        Args:
            csv_data (list[dict]): A list of dicts representing csv file rows.

        Raises:
            KeyError: If "lot", "condition", "desc", or "title" keys
                are not present in dicts of 'csv_data'.
        """

        for csv_line in self.data:
            if csv_line["desc"].find("  ") > -1:
                self._add_lot_warning(csv_line["lot"], "Double space found.")
            if not csv_line["desc"].endswith(('.', ')')):
                self._add_lot_warning(csv_line["lot"], "Description ends with a character other than '.' or ')'.")

            if not csv_line["condition"].endswith(('.', ')')):
                self._add_lot_warning(csv_line["lot"], "Condition ends with a character other than '.' or ')'.")

            if not csv_line["desc"].isascii():
                self._add_lot_warning(csv_line["lot"], "Description contains non-ASCII character(s).")

            if not csv_line["condition"].isascii():
                self._add_lot_warning(csv_line["lot"], "Condition contains non-ASCII character(s).")

            if not csv_line["desc"].isprintable():
                self._add_lot_warning(csv_line["lot"], "Description contains unprintable character(s).")

            if not csv_line["condition"].isprintable():
                self._add_lot_warning(csv_line["lot"], "Condition contains unprintable character(s).")

            if len(csv_line["title"]) > 60:
                self._add_lot_warning(csv_line["lot"], "Title longer than 60 characters.")


    # TODO: print warnings in lot-order (not alphabetically or in dict order)
    def generate_warning_log(self, path: str):
        """Generates a logfile of lot warnings at location specified by 'path'.

        Exports the contents of lot_warnings to a text file.
        NOTE: Be sure the file specified by 'path' does not exist or is OK to
            be overwritten, as this file does not check before overwriting.

        Args:
            path (str): Desired path for the logfile to be written to.

        Returns:
            None

        Raises:
            ?
        """

        warningCount = self.count_warnings()

        with open(path, "w") as log_file:
            log_file.write(80 * '#' + '\n')
            log_file.write("   AuctionFlex .csv Processor v0.1   ".center(80) + '\n')
            log_file.write("   ~ Warnings ~   ".center(80) + '\n')
            log_file.write(f"   ({warningCount} issues found)   ".center(80) + '\n')
            log_file.write(80 * '#' + '\n\n')

            # TODO: Add timestamp
            log_file.write("[Timestamp]\n\n")

            for lot in self.lot_warnings:
                log_file.write(f"Lot {lot}  ".ljust(80, '-') + '\n')
                for warning in self.lot_warnings[lot]:
                    log_file.write('   > ' + warning + '\n')

                log_file.write('\n')


    def split_lot_ext(self):
        """Separates numeric and alpha lot components.

        Adds a new "lot_ext" entry to each dict in csv_data containing
        the alpha portion of "lot" (eg. lot=205A becomes lot=205 and lot_ext=A).

        Args:
            csv_data (list[dict]): A list of dicts representing csv file rows.

        Returns:
            list[dict]: 'csv_data', with the above changes applied.

        Raises:
            ValueError: If a lot contains non-terminating alpha characters.
        """

        for csv_line in self.data:
            if csv_line["lot"].isdecimal():
                csv_line["lot_ext"] = ""
            else:
                if csv_line["lot"][:-1].isdecimal() and csv_line["lot"][-1:].isalpha():
                    csv_line["lot_ext"] = csv_line["lot"][-1:].upper()
                    csv_line["lot"] = csv_line["lot"][:-1]
                else:
                    self._add_lot_warning(csv_line["lot"], "Lot number contains non-terminating A-Z character(s).")
                    raise ValueError("Unexpected alpha character(s) in lot number.")


    def export_invaluable(self, path):
        self.fix_descriptions()
        self.format_whitespace()
        self.find_errors()
        self.split_lot_ext()

        with open(path, "w", newline="") as inv_file:
            writer = csv.writer(inv_file)
            writer.writerow(self.inv_headers)

            for line in self.data:
                writer.writerow([line["lot"], line["lot_ext"], line["title"], line["desc"], line["loEst"], line["hiEst"],
                                 line["startBid"], line["condition"]])

        if self.count_warnings() > 0:
            # TODO: indicate to user that issues were identified & logfile created
            self.generate_warning_log("proc_log.txt")


    # TODO: uppercase alpha lot characters (eg. 205A not 205a)
    def export_liveauctioneers(self, path):
        self.fix_descriptions()
        self.format_whitespace()
        self.find_errors()

        with open(path, "w", newline="") as la_file:
            writer = csv.writer(la_file)
            writer.writerow(self.la_headers)

            for line in self.data:
                writer.writerow([line["lot"], line["title"], line["desc"], line["loEst"], line["hiEst"], line["startBid"],
                                 line["condition"]])

        if self.count_warnings() > 0:
            # TODO: indicate to user that issues were identified & logfile created
            self.generate_warning_log("proc_log.txt")


################################################################################################################
#### Playground code

# inv_data = load_af_csv("afexp1.csv", af_headers)
# la_data = copy.deepcopy(inv_data)

# export_invaluable("inval_export.csv", inv_data)
# export_liveauctioneers("la_export.csv", la_data)

###################################################################################################################
