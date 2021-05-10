from tkinter import *
from tkinter import ttk
import csv
import json
from tkinter import messagebox
import os.path

from src.csvproc.csvproc import CSVProc
from src import CONF


class SettingsWindow:

    def __init__(self, main_window, processor: CSVProc, source_path: str, *, save_success_callback):
        self.window = Toplevel(main_window)
        self.processor = processor
        self._save_success_callback = save_success_callback
        self.window.title("CSV Display GUI, beta 1")
        self.settings_filename = "config.json"
        self.source_path = source_path
        self.heading_popup_isopen = False

        self._setup_GUI()

        # get the set of available column headers from the processor
        self.unused_headers = self.processor.af_headers
        self.used_headers = set()
        self.processor.src_path = self.source_path

        self._populate_table()

        # TODO: print to somewhere else
        # load settings from previously opened settings window and/or "sticky"
        # configuration settings from config.json file.
        if self._load_settings():
            print("Settings load successful")
        else:
            print("Settings load failed :(")

        self.window.mainloop()


    def _setup_GUI(self):
        self.last_click_x = -1
        self.last_click_y = -1

        width = 900
        height = 350
        ws = self.window.winfo_screenwidth()
        hs = self.window.winfo_screenheight()
        x = (ws / 2) - (width / 2)
        y = (hs / 2) - (height / 2)
        # TODO: change x var to 'x' (not 100)
        self.window.geometry("%dx%d+%d+%d" % (width, height, 100, y))

        self.main_frame = ttk.Frame(self.window, padding="10 5")
        self.main_frame.grid(column=0, row=0, sticky=(N, W, E, S))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        self.table_frame = ttk.Frame(self.main_frame)
        self.table_frame.grid(row=0, column=0, sticky=(N, W, E, S))
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)
        self.table_frame.rowconfigure(1, weight=1)
        self.table_frame.rowconfigure(2, weight=1)

        self.table_instruct_lbl = ttk.Label(self.table_frame, text="Double-click column header cells to assign column names")
        self.table_instruct_lbl.grid(row=0, column=0, sticky=(N, W))
        self.table = ttk.Treeview(self.table_frame, padding=(5, 5, 5, 5), height=4)
        self.table.grid(row=1, column=0, sticky=(S, W, E))
        self.table_scrollbar = ttk.Scrollbar(self.table_frame, orient=HORIZONTAL, command=self.table.xview)
        self.table_scrollbar.grid(row=2, column=0, sticky=(N, W, E))
        self.table.configure(xscrollcommand=self.table_scrollbar.set)

        self.settings_frame = ttk.Frame(self.main_frame)
        self.settings_frame.grid(row=1, column=0, sticky=(N, W, E, S))
        self.settings_frame.columnconfigure(0, weight=1)
        self.settings_frame.columnconfigure(1, weight=1)
        self.settings_frame.rowconfigure(0, weight=1)

        self.condition_frame = ttk.LabelFrame(self.settings_frame, text="Condition Reports", padding=5)
        self.condition_frame.grid(sticky=(N, W))
        self.condition_frame.columnconfigure(0, weight=1)
        self.condition_frame.rowconfigure(0, weight=1)
        self.condition_frame.rowconfigure(1, weight=1)

        self.condition_report_txt = Text(self.condition_frame, width=60, height=8, state="disabled")
        self.condition_report_txt.grid(row=1, column=0, sticky=W)
        self.using_bp_cond_str = StringVar()
        self.boiler_cond_chkbx = ttk.Checkbutton(self.condition_frame,
                                                 text="Use boilerplate condition report for all lots",
                                                 variable=self.using_bp_cond_str, command=self._boiler_cond_toggled, onvalue="yes",
                                                 offvalue="no")
        self.boiler_cond_chkbx.grid(row=0, column=0, sticky=W)

        self.options_frame = ttk.Frame(self.settings_frame)
        self.options_frame.grid(row=0, column=1, sticky=(N, E, S, W), pady=(10,0))
        self.options_frame.columnconfigure(0, weight=1)
        self.options_frame.rowconfigure(0, weight=1)
        self.options_frame.rowconfigure(1, weight=1)
        self.startbid_frame = ttk.Frame(self.options_frame)
        self.startbid_frame.grid(row=0, column=0, sticky=(N, W, E))
        self.startbid_frame.columnconfigure(0, weight=1)
        self.startbid_frame.rowconfigure(0, weight=1)
        self.startbid_frame.rowconfigure(1, weight=1)

        self.calc_startbid_var = StringVar()
        self.calc_startbid_chkbx = ttk.Checkbutton(self.startbid_frame,
                                                   text="Calculate StartBid as half of LoEst",
                                                   variable=self.calc_startbid_var, command=self._calc_startbid_toggled,
                                                   onvalue="yes", offvalue="no")
        self.calc_startbid_chkbx.grid(row=0, column=0, sticky=W)
        self.calc_empty_startbids_var = StringVar()
        self.calc_empty_startbids_chkbx = ttk.Checkbutton(self.startbid_frame,
                                                          text="Only calculate for lots without set StartBid",
                                                          variable=self.calc_empty_startbids_var,
                                                          command=self._calc_empty_startbids_toggled,
                                                          onvalue="yes", offvalue="no", state="disabled")
        self.calc_empty_startbids_chkbx.grid(row=1, column=0, sticky=W, padx=(20, 0))

        self.save_btn = ttk.Button(self.options_frame, text="Save", command=lambda: self._save_settings())
        self.save_btn.grid(row=1, column=0, sticky=(S, E))

        # TODO: might not want default 'close' behavior to be 'save settings'... change this or the saveBtn callback
        # self.window.protocol("WM_DELETE_WINDOW", lambda: self._save_settings())
        self.window.bind('<Button-1>', self._get_click_xy)

        # add some padding around each UI element in mainframe
        for child in self.main_frame.winfo_children():
            child.grid_configure(padx=5, pady=5)


    def _boiler_cond_toggled(self):
        if self.using_bp_cond_str.get() == "yes":
            self.condition_report_txt['state'] = 'normal'
        else:
            self.condition_report_txt['state'] = 'disabled'


    def _calc_startbid_toggled(self):
        if self.calc_startbid_var.get() == "yes":
            self.calc_empty_startbids_chkbx['state'] = 'normal'
            self.processor.calc_startbid = True
        else:
            self.calc_empty_startbids_chkbx['state'] = 'disabled'
            self.processor.calc_startbid = False


    def _calc_empty_startbids_toggled(self):
        if self.calc_startbid_var.get() == "yes" and self.calc_empty_startbids_var.get() == "yes":
            self.processor.calc_empty_startbids = True
        else:
            self.processor.calc_empty_startbids = False


    def _populate_table(self):
        """Fills the treeview (table) with data from first 4 lines of processor's file.
        """
        data = self.processor.get_n_rows(4)

        # this step creates the columns of the table;
        # column names are for internal reference (not displayed anywhere)
        column_names = []
        for col in range(self.processor.file_num_cols):
            column_names.append(f"col{col}")

        self.table["columns"] = column_names

        # column '#0' is a special column containing row numbers
        self.table.column("#0", width=30, stretch=FALSE)

        # set headers (if previously defined) for each column of the table
        for col in range(self.processor.file_num_cols):
            self.table.heading(col, command=lambda c=col: self.set_col_header(c))

        # place row numbers in column '#0'
        row_num = 1
        for r in data:
            self.table.insert('', "end", text=f'({row_num})', values=r)
            row_num += 1

        for col in range(self.processor.file_num_cols):
            # look at the lengths of each value in the first row of the csv to set column width accordingly
            if len(data[1][col].strip()) < 10:
                self.table.column(col, width=55, minwidth=55, stretch=FALSE)
            else:
                self.table.column(col, minwidth=100, width=100)


    def set_col_header(self, colNum):
        """Creates a popup prompt for user to select a column header from the list.

        Args:
            colNum: the index of the treeview (table) column to set the header for.
        """
        if self.heading_popup_isopen:
            return

        # prevent multiple heading-set popups from being open at once
        self.heading_popup_isopen = True
        popup = Toplevel(self.window)
        popup.title("Set col. header:")
        popup.attributes("-topmost", TRUE)  # keep popup on top of settings window
        popup.protocol("WM_DELETE_WINDOW", lambda p=popup: self._release_popup_lock(p))

        # place the popup approximately over the specified col header
        #   to enable "double click to set"-like behavior
        root_geom = self.window.geometry()
        popup_geom = root_geom[root_geom.find('+'):].split('+')[1:]
        #TODO: maybe make this a little less magic-numbery?
        popup.geometry(f"+{int(popup_geom[0]) + self.last_click_x - 75}+{int(popup_geom[1]) + self.last_click_y + 15}")
        popup.resizable(FALSE, FALSE)
        popup.lift(self.window)

        # create the dropdown menu for header selection
        header_var = StringVar()
        header = ttk.Combobox(popup, textvariable=header_var)
        header["values"] = sorted(list(self.unused_headers), key=str.lower)
        header.state(["readonly"])
        header.bind("<<ComboboxSelected>>",
                    lambda _, c=colNum, h=header_var, p=popup: self._set_col_header_helper(column=c, header=h,
                                                                                          popup=p))
        header.grid()


    def _set_col_header_helper(self, *, column: int, header: StringVar, popup: Toplevel):
        """Sets treeview column header text based on parameters.
        Function is called when a header is selected from the popup's dropdown.
        Sets of used/unused headers are also maintained here.

        Args:
            column: the index for the column to modify.
            header: var containing user's header selection from popup dropdown.
            popup: handle to the popup window object itself.
        """
        #
        headerText = header.get()
        ht = self.table.heading(column, option="text")

        # if there is a header already assigned to the specified column,
        #   add it back to the unused_headers set.
        if len(ht) > 1:
            self.unused_headers.add(ht)

        # header "None" doesn't behave like the other headers in that it shouldn't be removed
        #   when selected (to avoid "gridlock" when all columns have headers assigned)
        if headerText != "[None]":
            self.table.heading(column, text=headerText)
            self.unused_headers.remove(headerText)
            self.used_headers.add(headerText)
        else:
            # when changing a header to "None", it's existing text should be
            # added back into the set of unusedHeaders
            self.table.heading(column, text="")

        popup.destroy()
        self.heading_popup_isopen = False   # allow new popups to spawn


    def _release_popup_lock(self, popup):
        popup.destroy()
        self.heading_popup_isopen = False


    def _load_settings(self):
        """Loads saved configuration from file.

        Returns: True if load was successful, False if not.
        """
        # load table headers from processor
        table_headers = self.processor.file_headers

        if len(table_headers) != self.processor.file_num_cols and len(table_headers) != 0:
            # mismatch between number of headers in processor and num columns in table
            print(f"Len table headers {len(table_headers)}; file_num_cols: {self.processor.file_num_cols}")
            return False
        elif len(table_headers) != 0:
            #TODO: I'm sure this could be done neater with an iterator of some sort
            h = 0
            for c in range(self.processor.file_num_cols):
                self.table.heading(c, text=table_headers[h])
                h += 1

        # load up a local copy of stored config data
        with open(self.settings_filename, 'r') as sf:
            config_data = json.load(sf)

        try:
            # enable text box for a moment in order to insert loaded boilerplate condition text
            self.condition_report_txt['state'] = 'normal'
            self.condition_report_txt.insert(1.0, config_data["bp_condition"])

            # convert boolean from config file to "yes"/"no" for checkbox variable
            if config_data["using_bp_condition"]:
                self.using_bp_cond_str.set("yes")
                self._boiler_cond_toggled()
            else:
                self.using_bp_cond_str.set("no")
                self._boiler_cond_toggled()
        except KeyError:
            # config file not what we expected?
            # TODO: replace with error message printed to mainwindow or _display_errorbox
            print("Error loading config file: key not found.")
            return False

        # indicate successful settings load to the caller
        return True


    def _get_click_xy(self, event):
        self.last_click_x = event.x
        self.last_click_y = event.y


    def _save_settings(self):
        """Saves current settings to CSVProc processor & config file (where appropriate).

        Returns: nothing (but SettingsWindow is destroyed)
        """
        try:
            self._validate_settings()
            self.processor.set_file_col_headers(self.get_table_headers())
        except RuntimeError as e:
            self._display_errorbox(f"Save error: {e}")
            return

        using_bp_cond_bool = True if self.using_bp_cond_str.get() == "yes" else False

        # set processor member vars to local values
        self.processor.using_bp_condition = using_bp_cond_bool
        self.processor.bp_condition = self.get_bp_condition_text()

        # additionally, save reusable settings to config file (for next time)
        config_data = {CONF.USING_BP_COND: using_bp_cond_bool,
                       CONF.BP_COND: self.get_bp_condition_text()}

        with open(self.settings_filename, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        # enable "process" button in main window
        self._save_success_callback()

        self.window.destroy()


    def _validate_settings(self):
        """Checks validity/compatibility of various settings.
        Errors are indicated with the raising of RuntimeErrors.

        Returns: True if all validation tests succeed.
        """
        # make sure every column is labeled with a header
        for c in range(self.processor.file_num_cols):
            if not self.table.heading(c, option="text").strip():
                raise RuntimeError("Unlabeled column header(s)")

        # if BP Condition checkbox is checked, make sure text box has some text in it
        if self.using_bp_cond_str.get() == "yes" and not self.get_bp_condition_text():
            raise RuntimeError("Boilerplate condition report empty")

        # if all tests passed, return true
        return True


    def get_bp_condition_text(self) -> str:
        # just a wrapper for some ugly syntax
        return self.condition_report_txt.get(1.0, END).strip()


    def get_table_headers(self) -> list:
        column_headers = []

        for c in range(self.processor.file_num_cols):
            heading = self.table.heading(c, option="text")
            column_headers.append(heading)

        return column_headers


    def _display_errorbox(self, text):
        messagebox.showerror(message=text)
