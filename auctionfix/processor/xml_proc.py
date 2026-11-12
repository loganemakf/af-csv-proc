# XMLProc.py
# AuctionFix - post-processor for exported auction catalogs
# Copyright (C) 2026  Logan Foster

import logging
import xml.etree.ElementTree as ET
import pathlib, csv, copy, re
from pathlib import Path
from .base import AFProcessor
from ..labels import LabelOptions, make_labels as make_label_pdf

log = logging.getLogger(__name__)


class XMLProc(AFProcessor):
    # specialize af_headers for XML files: one "Desc" field in place of "Desc. 1"-"Desc. 5" (a new list, so CSVProc
    # keeps its own)
    af_headers = (
        AFProcessor.af_headers[:2]
        + ["Desc"]
        + [h for h in AFProcessor.af_headers[2:] if not h.startswith("Desc. ")]
    )

    af_to_xml_tag_map = {
        "LotNum": "lotnum",
        "Title": "lead",
        "Desc": "description",
        "LoEst": "presaleestmin",
        "HiEst": "presaleestmax",
        "StartBid": "startbideach",
        "Condition": "udfield12",
        "Height": "udfield22",
        "Width": "udfield23",
        "Depth": "udfield24",
        "DimUnit": "udfield25",
        "Weight": "udfield26",
        "WtUnit": "udfield1",
        "Reserve": "reserveeach",
        "Qty": "quantity",
        "Consign#": "ccode",
        "Ref#": "udfield21",
        "Inv#": "inventorynum",
    }

    xml_to_af_tag_map = {v: k for k, v in af_to_xml_tag_map.items()}

    def __init__(self):
        super().__init__()

    def load_af_xml(self):
        tree = ET.parse(self.src_path)
        root = tree.getroot()
        headers_present = set()
        for lot in root:
            lot_dict = {}
            for field in lot:
                try:
                    field_key = self.xml_to_af_tag_map[field.tag]
                    headers_present.add(field_key)
                    lot_dict[field_key] = (field.text or "").strip()
                    # print(f"{field_key}: {field.text or ''}")
                except KeyError:
                    log.debug("No mapping for XML field %r; skipping", field.tag)
            self.data.append(lot_dict)
        self.export_file_headers = [h for h in self.af_headers if h in headers_present]

    def _check_related_columns(self, data: list):
        """Checks that related columns exist and, when one of a pair is filled in, the other is as well.
        Logs warnings as appropriate.

        Args:
            data: A list of dicts representing csv file rows.
        """
        for record in data:
            # if H, W, or D are defined, dimension unit should also be defined (and vice-versa)
            if (
                any(
                    [
                        len(record[field]) > 0
                        for field in ("Height", "Width", "Depth")
                        if field in self.export_file_headers
                    ]
                )
                and "DimUnit" in self.export_file_headers
                and len(record["DimUnit"]) == 0
            ):
                self._add_lot_warning(record["LotNum"], "Missing dimension unit.")
            elif "DimUnit" in self.export_file_headers and len(record["DimUnit"]) > 0:
                # print(f"{record['LotNum']}: {len(record['DimUnit'])=}")
                if not any(
                    [
                        len(record[field]) > 0
                        for field in ("Height", "Width", "Depth")
                        if field in self.export_file_headers
                    ]
                ):
                    self._add_lot_warning(
                        record["LotNum"],
                        "DimUnit specified but co-requisite H/W/D field(s) are not.",
                    )

            # if Weight is defined, weight unit should be as well (and vice versa)
            if "Weight" in self.export_file_headers and len(record["Weight"]) > 0:
                if "WtUnit" in self.export_file_headers and len(record["WtUnit"]) == 0:
                    self._add_lot_warning(record["LotNum"], "Missing weight unit.")
            elif "WtUnit" in self.export_file_headers and len(record["WtUnit"]) > 0:
                if "Weight" in self.export_file_headers and len(record["Weight"]) > 0:
                    self._add_lot_warning(
                        record["LotNum"],
                        "WtUnit specified but co-requisite Weight column is not.",
                    )
            # todo: AFProcessor checks consignor#/ref# -- not sure if it makes sense to replicate that here

    def _process_conditions(self, data: list):
        """Handles condition report truncation warning & boilerplate condition report substitution."""
        if self.using_bp_condition:
            for record in data:
                record["Condition"] = self.bp_condition
        elif "Condition" in self.export_file_headers:
            for record in data:
                # todo: hopefully this is not necessary with XML, but leaving it for now just in case
                self._log_error_if(
                    len(record["Condition"]) == 221,
                    record,
                    "Condition has likely been cut off by "
                    "AuctionFlex during export.",
                )

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
                self._add_lot_warning(
                    record["LotNum"],
                    "Double space found (should be impossible after _format_whitespace(), "
                    "but here we are).",
                )
            if (not record["Desc"].endswith((".", ")"))) and len(record["Desc"]) > 700:
                warning = (
                    f"Description ends with a character other than '.' or ')' (last character: "
                    f"'{record['Desc'][-1] if len(record['Desc']) > 0 else ''}') (Length: {len(record['Desc'])})"
                )
                # warning = (
                #     f"{warning} -- likely cut-off!)."
                #     if len(record["Desc"]) > 700
                #     else f"{warning})."
                # )
                self._add_lot_warning(record["LotNum"], warning)
            if not record["Desc"].isascii():
                self._add_lot_warning(
                    record["LotNum"], "Description contains non-ASCII character(s)."
                )
            # if not record["Desc"].isprintable():
            #     self._add_lot_warning(
            #         record["LotNum"], "Description contains unprintable character(s)."
            #     )
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
                except KeyError | ValueError:
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
                # self._log_error_if(
                #     not record["Condition"].isprintable(),
                #     record,
                #     "Condition contains unprintable " "character(s).",
                # )
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
                    "StartBid greater than high estimate.",
                )

    @staticmethod
    def _convert_numeric_to_int(data: list):
        # determine which numeric fields are present in 'data'
        integer_fields = ["LoEst", "HiEst", "StartBid", "Qty", "Reserve"]
        for field in integer_fields:
            if field not in data[0].keys():
                integer_fields.remove(field)

        # convert numeric fields from strings to integers
        for record in data:
            for field in integer_fields:
                # for XML files, we must check the length of the (stripped) field before attempting to convert
                if len(str(record[field])) > 0:
                    record[field] = int(float(record[field]))

    @staticmethod
    def _replace_descr_newlines_with_br_tags(data: list):
        for record in data:
            if "Desc" not in record.keys():
                raise RuntimeError(f"Description not found for lot {record["LotNum"]}")

            record["Desc"] = re.sub(r"\n", r"<br>", record["Desc"])

    def _export_invaluable(
        self, data: list, progress_callback, error_callback, skip_export: bool = False
    ):
        filename = "XML_Invalu_Export_" + self._get_timestamp() + ".csv"
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
            # todo: _c_r_c only checks the headers for the first lot; should extend to cover each lot individually
            self._check_related_columns(data)
            progress_callback(11)
            # todo: do we need to worry about cut-off conditions for XML exports?
            self._process_conditions(data)
            progress_callback(14)
            self._process_startbids(data)
            progress_callback(17)
            # todo: will this remove newlines?
            self._format_whitespace(data)
            progress_callback(20)
            self._find_errors(data)
            progress_callback(23)
            self._split_lot_ext(data)
            progress_callback(26)
            self._convert_numeric_to_int(data)
            # add missing export headers works fine as-is because all dicts in self.data have the same keys
            self._add_missing_export_headers(data)

            # NEW - February 2026
            self._fix_empty_descriptions(data)
            self._fix_spaced_hyphenation(data)
            self._replace_descr_newlines_with_br_tags(data)

            self._fix_unsupported_chars(data)
            # self._check_title_quantities(data)

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
                    # if line["LotNum"] == "424":
                    # print(f"{line=}")
                    # map AFlex header keys to Invaluable header keys
                    new_line = {
                        self.inv_headers[key]: val
                        for (key, val) in line.items()
                        if key in self.inv_headers.keys()
                    }
                    # if line["LotNum"] == "424":
                    #     print(f"{new_line=}")
                    writer.writerow(new_line)

        else:
            error_callback(
                "Non-numeric value encountered in a numeric field; export aborted."
            )

    def _export_liveauctioneers(
        self, data: list, progress_callback, error_callback, skip_export: bool = False
    ):
        filename = "XML_LiveAuc_Export_" + self._get_timestamp() + ".csv"
        path = self.dest_path / filename

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
            # this was omitted from LA export previously -- why?
            self._convert_numeric_to_int(data)
            self._add_missing_export_headers(data)
            progress_callback(63)
            # self._check_title_quantities(data)

            # NEW! February 2026
            self._fix_empty_descriptions(data)
            self._fix_spaced_hyphenation(data)
            self._replace_descr_newlines_with_br_tags(data)

            self._fix_unsupported_chars(data)

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
        label_footer="",
        label_layout="avery5160",
        label_options=None,
    ):
        # load data from the catalog .csv file into self.data
        proc_filename = "Processor_Data_" + self._get_timestamp() + ".csv"
        proc_file_path = self.dest_path / proc_filename
        # todo: this is a member of CSVProc only -- need to generalize
        # self.get_n_rows(1)
        if use_proc_file:
            self.load_proc_csv(self.src_path)
        else:
            # todo: also a member of CSVProc
            # self._load_af_csv()
            self.load_af_xml()
        progress_callback(0.0)

        self._uppercase_lotnums(self.data)
        # if not use_proc_file:
        # todo: also a member of CSVProc only
        # self._fix_descriptions()

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

            if make_labels:
                make_label_pdf(
                    self.data,
                    self.dest_path / f"labels_{self._get_timestamp()}.pdf",
                    label_layout,
                    label_options or LabelOptions(label_footer=label_footer),
                )

            # setting progressbar value to 99+ makes it appear full (whereas 100 looks empty)
            progress_callback(99.99)
        except RuntimeError:
            progress_callback(0.0)
