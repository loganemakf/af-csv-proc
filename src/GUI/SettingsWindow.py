from tkinter import *
from tkinter import ttk
import csv
import json
from tkinter import messagebox
import os.path

from src.csvproc.csvproc import CSVProc


class SettingsWindow:

    def __init__(self, main_window, processor: CSVProc, source_path: str):
        self.processor = processor
        self.window = Toplevel(main_window)
        self.window.title("CSV Display GUI, beta 1")
        # root.resizable(FALSE, FALSE)

        self.settings_filename = "config.json"
        self.source_path = source_path
        self.heading_popup_isopen = False

        self._setup_GUI()

        self.unused_headers = self.processor.af_headers
        self.used_headers = set()
        self.processor.src_path = self.source_path

        self._populate_table()

        # load settings from previously opened settings window and/or "sticky"
        # configuration settings from config.json file.
        if self._load_settings():
            print("Settings load successful")
        else:
            print("Settings load failed :(")

        # add some padding around each UI element in mainframe
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

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

        self.mainframe = ttk.Frame(self.window, padding="10 5")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        self.mainframe.columnconfigure(0, weight=1)
        self.mainframe.rowconfigure(0, weight=1)
        self.mainframe.rowconfigure(1, weight=1)
        self.tableFrame = ttk.Frame(self.mainframe)
        self.tableFrame.grid(row=0, column=0, sticky=(N, W, E, S))
        self.tableFrame.columnconfigure(0, weight=1)
        self.tableFrame.rowconfigure(0, weight=1)
        self.tableFrame.rowconfigure(1, weight=1)

        self.table = ttk.Treeview(self.tableFrame, padding=(5, 5, 5, 5), height=4)
        self.table.grid(row=0, column=0, sticky=(S, W, E))
        self.scb = ttk.Scrollbar(self.tableFrame, orient=HORIZONTAL, command=self.table.xview)
        self.scb.grid(row=1, column=0, sticky=(N, W, E))
        self.table.configure(xscrollcommand=self.scb.set)

        self.settingsFrame = ttk.Frame(self.mainframe)
        self.settingsFrame.grid(row=1, column=0, sticky=(N, W, E, S))
        self.settingsFrame.columnconfigure(0, weight=1)
        self.settingsFrame.columnconfigure(1, weight=1)
        self.settingsFrame.rowconfigure(0, weight=1)

        self.frame_condition = ttk.LabelFrame(self.settingsFrame, text="Condition Reports", padding=5)
        self.frame_condition.grid(sticky=(N, W))
        self.frame_condition.columnconfigure(0, weight=1)
        self.frame_condition.rowconfigure(0, weight=1)
        self.frame_condition.rowconfigure(1, weight=1)

        self.condition_report_text = Text(self.frame_condition, width=60, height=6, state="disabled")
        self.condition_report_text.grid(row=1, column=0, sticky=W)
        self.using_bp_cond_str = StringVar()
        self.chkbox_bp_cond = ttk.Checkbutton(self.frame_condition,
                                              text="Use boilerplate condition report for all lots",
                                              variable=self.using_bp_cond_str, command=self._bpcond, onvalue="yes",
                                              offvalue="no")
        self.chkbox_bp_cond.grid(row=0, column=0, sticky=W)

        self.btn_save = ttk.Button(self.settingsFrame, text="Save", command=lambda: self._save_settings())
        self.btn_save.grid(row=0, column=1, sticky=(N, E))

        # TODO: might not want default 'close' behavior to be 'save settings'... change this or the saveBtn callback
        # self.window.protocol("WM_DELETE_WINDOW", lambda: self._save_settings())
        self.window.bind('<Button-1>', self._get_click_xy)


    def _populate_table(self):
        data = self.processor.get_n_rows(4)

        column_names = []
        for col in range(self.processor.file_num_cols):
            column_names.append(f"col{col}")

        self.table["columns"] = column_names

        self.table.column("#0", width=30, stretch=FALSE)

        for col in range(self.processor.file_num_cols):
            self.table.heading(col, command=lambda c=col: self.set_col_header(c))

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


    def _load_settings(self):
        # load table headers from CSVProc instance
        table_headers = self.processor.file_headers

        if len(table_headers) != self.processor.file_num_cols:
            # mismatch between number of headers in processor and num columns in table
            # return False
            pass
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
            # enable text box for a moment in order to insert loaded condition text
            self.condition_report_text['state'] = 'normal'
            self.condition_report_text.insert(1.0, config_data["bp_condition"])

            # convert boolean from config file to "yes"/"no" for checkbox variable
            if config_data["using_bp_condition"]:
                self.using_bp_cond_str.set("yes")
                self._bpcond()
            else:
                self.using_bp_cond_str.set("no")
                self._bpcond()

            print("BP Condition textbox should NOT be empty now")
            print(f'(should contain: {config_data["bp_condition"]})')
        except KeyError:
            # config file not what we expected?
            print("Error loading config file: key not found.")
            return False

        # indicate successful settings load to the caller
        return True


    def peek_first_rows(self, path: str) -> list:
        lot_data = []

        with open(path, "r", encoding="latin-1", newline="") as af_file:
            reader = csv.reader(af_file)
            lineCount = 0
            for line in reader:
                if lineCount < 4:
                    lineCount += 1
                    lot_data.append(line)
                else:
                    break

        return lot_data


    def _get_click_xy(self, event):
        self.last_click_x = event.x
        self.last_click_y = event.y


    def _release_popup_lock(self, popup):
        popup.destroy()
        self.heading_popup_isopen = False


    def set_col_header(self, colNum):
        if self.heading_popup_isopen:
            return

        self.heading_popup_isopen = True
        popup = Toplevel(self.window)
        popup.title("Set col. header:")
        popup.attributes("-topmost", TRUE)
        popup.protocol("WM_DELETE_WINDOW", lambda p=popup: self._release_popup_lock(p))

        root_geom = self.window.geometry()
        popup_geom = root_geom[root_geom.find('+'):].split('+')[1:]
        #TODO: maybe make this a little less magic-numbery?
        popup.geometry(f"+{int(popup_geom[0]) + self.last_click_x - 75}+{int(popup_geom[1]) + self.last_click_y + 15}")
        popup.resizable(FALSE, FALSE)
        popup.lift(self.window)

        headerVar = StringVar()
        header = ttk.Combobox(popup, textvariable=headerVar)
        header["values"] = sorted(list(self.unused_headers), key=str.lower)
        header.state(["readonly"])
        header.bind("<<ComboboxSelected>>",
                    lambda _, c=colNum, h=headerVar, p=popup: self._set_col_header_helper(_, column=c, header=h,
                                                                                         popup=p))
        header.grid()


    def _set_col_header_helper(self, *args, column, header, popup):
        headerText = header.get()
        # "None" doesn't behave like the other options in that it shouldn't
        # be removed when selected (to avoid deadlocking the selected fields)
        ht = self.table.heading(column, option="text")
        if len(ht) > 1:
            self.unused_headers.add(ht)

        if headerText != "[None]":
            self.table.heading(column, text=headerText)
            self.unused_headers.remove(headerText)
            self.used_headers.add(headerText)
        else:
            # when changing a header to "None", it's existing text should be
            # added back into the set of unusedHeaders
            self.table.heading(column, text="")

        popup.destroy()
        self.heading_popup_isopen = False


    def _bpcond(self):
        if self.using_bp_cond_str.get() == "yes":
            self.condition_report_text['state'] = 'normal'
        else:
            self.condition_report_text['state'] = 'disabled'


    def get_table_headers(self) -> list:
        column_headers = []

        for c in range(self.processor.file_num_cols):
            heading = self.table.heading(c, option="text")
            column_headers.append(heading)
        #TODO: no need to print this
        print(column_headers)
        return column_headers


    def get_bp_condition_text(self) -> str:
        return self.condition_report_text.get(1.0, END).strip()


    def _save_settings(self):
        # save current settings to CSVProc object
        try:
            self._validate_settings()
            self.processor.set_file_col_headers(self.get_table_headers())
        except RuntimeError as e:
            self._display_errorbox(f"Save error: {e}")
            return

        using_bp_cond_bool = True if self.using_bp_cond_str.get() == "yes" else False

        self.processor.using_bp_condition = using_bp_cond_bool
        self.processor.bp_condition = self.get_bp_condition_text()

        # additionally, save reusable settings to config file (for next time)
        config_data = {}

        if using_bp_cond_bool:
            config_data["using_bp_condition"] = True
        else:
            config_data["using_bp_condition"] = False

        config_data["bp_condition"] = self.get_bp_condition_text()
        print(f'BP condition text (writing to json): {config_data["bp_condition"]}')

        with open(self.settings_filename, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        self.window.destroy()


    def _validate_settings(self):
        # make sure every column is labeled with a header
        for c in range(self.processor.file_num_cols):
            if not self.table.heading(c, option="text").strip():
                raise RuntimeError("Unlabeled column header")

        # if BP Condition checkbox is checked, make sure text box has some text in it
        if self.using_bp_cond_str.get() == "yes" and not self.get_bp_condition_text():
            raise RuntimeError("Boilerplate condition report empty")

        # if all tests passed, return true
        return True


    def _display_errorbox(self, text):
        messagebox.showerror(message=text)
