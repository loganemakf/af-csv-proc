# CSVProc.py
# AuctionFix - post-processor for exported auction catalogs
# Copyright (C) 2021  Logan Foster

import csv
import copy
import os.path
from pathlib import Path

from .base import AFProcessor

from .. import C


class CSVProc(AFProcessor):
    def __init__(self, src_path: str | Path = "", dest_path: str | Path = ""):
        super().__init__()
        self.file_headers = (
            []
        )  # subset of af_headers corresponding to columns in catalog .csv file
        self.src_path = Path(src_path)  # the catalog .csv file
        self.dest_path = Path(
            dest_path
        )  # a folder to save exported LiveAuctioneers/Invaluable .csv (and log) files in

    @staticmethod
    def test_open(src_path: Path):
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
        if not self.src_path.exists():
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
            raise RuntimeError(
                f"Mismatched header/column count ({len(headers)} vs. {self.file_num_cols})."
            )

    def _load_af_csv(self, headers=None):
        """Reads in data from an AuctionFlex-exported .csv catalog file.

        Rows of the catalog file specified by self.src_path are stored as dicts in self.data.
        """
        if headers is None:
            headers = self.file_headers
        if len(headers) == 0 or len(headers) != self.file_num_cols:
            raise RuntimeError("Catalog load error: mismatch in header/column count.")

        with open(self.src_path, "r", encoding="latin-1", newline="") as af_file:
            self.data = []
            reader = csv.DictReader(af_file, fieldnames=headers)

            self.data = [line for line in reader]

    def _fix_descriptions(self):
        """Concatenates 'Desc. [1-5]' entries into a single dict entry, "Desc"."""
        for record in self.data:
            record["Desc"] = (
                record.pop("Desc. 1")
                + " "
                + record.pop("Desc. 2")
                + " "
                + record.pop("Desc. 3")
                + " "
                + record.pop("Desc. 4")
                + " "
                + record.pop("Desc. 5")
            )

        # insert new "Desc" header just before soon-to-be-removed "Desc. 1" header
        self.export_file_headers = self.file_headers.copy()
        desc_index = self.export_file_headers.index("Desc. 1")
        self.export_file_headers.insert(desc_index, "Desc")

        for i in range(1, 6):
            self.export_file_headers.remove(f"Desc. {i}")

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
            if not record["Desc"].endswith((".", ")")):
                warning = (
                    f"Description ends with a character other than '.' or ')' (last character: "
                    f"'{record['Desc'][-1] if len(record['Desc']) > 0 else ''}') (Length: {len(record['Desc'])}"
                )
                warning = (
                    f"{warning} -- likely cut-off!)."
                    if len(record["Desc"]) > 700
                    else f"{warning})."
                )
                self._add_lot_warning(record["LotNum"], warning)
            if not record["Desc"].isascii():
                self._add_lot_warning(
                    record["LotNum"], "Description contains non-ASCII character(s)."
                )
            if not record["Desc"].isprintable():
                self._add_lot_warning(
                    record["LotNum"], "Description contains unprintable character(s)."
                )
            if len(record["Title"]) > 60:
                self._add_lot_warning(
                    record["LotNum"], "Title longer than 60 characters."
                )

            # checks for optional fields
            if "LoEst" in record.keys() and "HiEst" in record.keys():
                lo_est = float(record["LoEst"])
                hi_est = float(record["HiEst"])
                if lo_est >= hi_est:
                    self._add_lot_warning(
                        record["LotNum"],
                        f"Low estimate (${lo_est:.2f}) greater than or equal to "
                        f"high estimate (${hi_est:.2f}).",
                    )
                try:
                    startbid = float(record["StartBid"])
                except ValueError:
                    startbid = lo_est / 2
                if lo_est < 5.00 or hi_est < 5.00 or startbid < 5.00:
                    self._add_lot_warning(
                        record["LotNum"], "Lo/HiEst or StartBid is below $5."
                    )

                # throw warning for high estimate 3+ times greater than low estimate
                if lo_est > 0:
                    self._log_error_if(
                        hi_est / lo_est > 3,
                        record,
                        f"High estimate (${hi_est:.2f}) exceeds low estimate (${lo_est:.2f}) by a factor "
                        f"of {hi_est/lo_est:.2f}.",
                    )

            if "Condition" in record.keys():
                self._log_error_if(
                    not record["Condition"].isprintable(),
                    record,
                    "Condition contains unprintable " "character(s).",
                )
                self._log_error_if(
                    not record["Condition"].isascii(),
                    record,
                    "Condition contains non-ASCII character(s).",
                )
                self._log_error_if(
                    not record["Condition"].endswith((".", ")")),
                    record,
                    "Condition ends with a character other than '.' or ')'.",
                )

            if "StartBid" in record.keys():
                self._log_error_if(
                    float(record["StartBid"]) > float(record["LoEst"]),
                    record,
                    "StartBid greater than low estimate.",
                )
                self._log_error_if(
                    float(record["StartBid"]) > float(record["HiEst"]),
                    record,
                    "StartBid greater than " "high estimate.",
                )

    # todo: this is needed for webapp integ., but won't be with XML processor
    # will require changes both here and in webapp, most likely
    def get_lots_with_truncated_descriptions(self) -> list:
        truncated_description_lots = list()
        for record in self.data:
            if not record["Desc"].strip().endswith((".", ")")):
                truncated_description_lots.append(record["LotNum"].strip())
        return truncated_description_lots

    @staticmethod
    def _fix_empty_descriptions(data: list):
        for record in data:
            if len(record["Desc"]) == 0:
                record["Desc"] = record["Title"]

    def _export_invaluable(
        self, data: list, progress_callback, error_callback, skip_export: bool = False
    ):
        filename = "Invalu_Export_" + self._get_timestamp() + ".csv"
        path = self.dest_path / filename

        # verify that required fields are all present
        try:
            self._check_required_columns(data, self.required_headers_inv)
        except RuntimeError as e:
            error_callback("Invaluable export error: " + str(e))
            raise e

        # process data for upload to Invaluable
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
            self._fix_empty_descriptions(data)
            self._fix_unsupported_chars(data)
            # self._check_title_quantities(data)

            if skip_export:
                return

            # create header row (for ordering purposes)
            exp_headers = [
                self.inv_headers[h]
                for h in self.export_file_headers
                if h in self.inv_headers
            ]
            progress_callback(29)

            with open(path, "w", newline="") as inv_file:
                writer = csv.DictWriter(inv_file, exp_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to Invaluable header keys
                    new_line = {
                        self.inv_headers[key]: val
                        for (key, val) in line.items()
                        if key in self.inv_headers.keys()
                    }
                    writer.writerow(new_line)

        else:
            error_callback(
                "Non-numeric value encountered in a numeric field; export aborted."
            )

    def _export_liveauctioneers(
        self, data: list, progress_callback, error_callback, skip_export: bool = False
    ):
        filename = "LiveAuc_Export_" + self._get_timestamp() + ".csv"
        path = os.path.join(self.dest_path, filename)

        # verify that required fields are all present
        try:
            self._check_required_columns(data, self.required_headers_la)
        except RuntimeError as e:
            error_callback("LiveAuctioneers export error: " + str(e))
            raise e

        # process data for upload to LiveAuctioneers
        progress_callback(48)
        if self._check_numeric_fields(data):
            self._check_dimension_fields(data)
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
            self._fix_empty_descriptions(data)
            progress_callback(63)
            # self._check_title_quantities(data)

            if skip_export:
                return

            # create header row (for ordering purposes)
            exp_headers = [
                self.la_headers[h]
                for h in self.export_file_headers
                if h in self.la_headers
            ]

            progress_callback(66)

            with open(path, "w", newline="") as la_file:
                writer = csv.DictWriter(la_file, exp_headers)
                writer.writeheader()
                for line in data:
                    # map AFlex header keys to LA header keys
                    new_line = {
                        self.la_headers[key]: val
                        for (key, val) in line.items()
                        if key in self.la_headers.keys()
                    }
                    writer.writerow(new_line)

        else:
            error_callback(
                "Non-numeric value encountered in a numeric field; export aborted."
            )

    def process(
        self,
        *,
        progress_callback,
        result_callback,
        use_proc_file=False,
        make_proc_file=False,
        skip_export=False,
        replacement_descriptions=None,
        make_labels=False,
    ):
        """Coordinates LA & Inv. catalog processing+export and warning log creation.

        Args:
            progress_callback: func. with int param for updating progressbar in MainWindow
            result_callback: func. with str param for displaying message to user after processing/export is done.
            use_proc_file: bool indicating whether the file at self.src_path was generated by keep_proc_file
            make_proc_file: boolean representing whether to retain a file containing the intermediate processing data
        """
        # load data from the catalog .csv file into self.data
        proc_filename = "Processor_Data_" + self._get_timestamp() + ".csv"
        proc_file_path = self.dest_path / proc_filename
        # todo: this is a member of CSVProc only -- need to generalize
        self.get_n_rows(1)
        if use_proc_file:
            self.load_proc_csv(self.src_path)
        else:
            # todo: also a member of CSVProc
            self._load_af_csv()
        progress_callback(0.0)

        self._uppercase_lotnums(self.data)
        if not use_proc_file:
            # todo: also a member of CSVProc only
            self._fix_descriptions()

        if replacement_descriptions:
            self._replace_descriptions(replacement_descriptions)
        progress_callback(2.5)  # set progress bar to 2.5%
        if make_proc_file:
            self.save_proc_csv(proc_file_path)

        inv_data = copy.deepcopy(self.data)
        la_data = copy.deepcopy(self.data)
        progress_callback(5)

        try:
            # process and export the catalog for upload to both bidding platforms
            self._export_invaluable(
                inv_data, progress_callback, result_callback, skip_export
            )
            progress_callback(45)
            self._export_liveauctioneers(
                la_data, progress_callback, result_callback, skip_export
            )
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
