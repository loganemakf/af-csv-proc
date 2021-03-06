# MainWindow.py
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

from tkinter import *
from tkinter import ttk, messagebox
from tkinter import filedialog as fd
import os.path
from src.GUI.SettingsWindow import SettingsWindow
from src.CSVProc.CSVProc import CSVProc
from src import C


class MainWindow:

    def __init__(self, root: Tk, processor: CSVProc):
        self.processor = processor
        self.window = root
        self.window.title(f"{C.PROGRAM_NAME}")
        self.window.resizable(FALSE, FALSE)
        self.src_path = ""
        self.dest_path = ""

        self._setup_GUI()

        self.window.protocol("WM_DELETE_WINDOW", self.shutdown_ttk_repeat)
        self.window.mainloop()


    def _setup_GUI(self):
        # (roughly) center main window
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        ws = self.window.winfo_screenwidth()
        hs = self.window.winfo_screenheight()
        x = (ws / 2) - width
        y = (hs / 2) - (height / 2)
        self.window.geometry("+%d+%d" % (x, y))

        self.main_frame = ttk.Frame(self.window, padding="30 15")
        self.main_frame.grid(column=0, row=0, sticky=(N, W, E, S))

        self.instructions_lbl = ttk.Label(self.main_frame, text="Select an AuctionFlex-exported .csv file to process",
                                          anchor="center")
        self.instructions_lbl.grid(column=0, row=0, columnspan=3)

        self.src_entry_var = StringVar()
        self.src_entry_var.set("No file selected")
        self.source_entry = ttk.Entry(self.main_frame, width=30, state="readonly", justify="center",
                                      textvariable=self.src_entry_var)
        self.source_entry.grid(column=0, row=1, columnspan=2, sticky=(W, E))
        self.src_entry_default_color = self.source_entry.cget("foreground")
        self.src_btn = ttk.Button(self.main_frame, text="Browse", command=self.get_source_file).grid(column=2, row=1,
                                                                                                     sticky=W)

        self.step2_frame = ttk.Frame(self.main_frame, padding=5)
        self.step2_frame.grid(column=0, row=2, columnspan=3, sticky=(E, W))
        self.step2_frame.columnconfigure(0, weight=1)
        self.step2_frame.columnconfigure(1, weight=1)
        self.step2_frame.columnconfigure(2, weight=1)
        self.step2_frame.columnconfigure(3, weight=1)
        self.step2_frame.columnconfigure(4, weight=1)
        self.step2_frame.rowconfigure(0, weight=1)

        self.settings_btn = ttk.Button(self.step2_frame, text="Settings", state=["disabled"],
                                       command=self.open_settings)
        self.settings_btn.grid(column=1, row=0, sticky=E)
        self.process_btn = ttk.Button(self.step2_frame, text="Process", state=["disabled"], command=self.get_dest_file)
        self.process_btn.grid(column=3, row=0, sticky=W)

        # progBar has 100 steps by default; update with currProg.set(val)
        self.curr_prog_var = DoubleVar()
        self.prog_bar = ttk.Progressbar(self.main_frame, variable=self.curr_prog_var, orient=HORIZONTAL, mode="determinate")
        self.prog_bar.grid(column=0, row=3, columnspan=3, sticky=(W, E))

        # add some padding around each UI element in mainframe
        for child in self.main_frame.winfo_children():
            child.grid_configure(padx=5, pady=5)


    def get_source_file(self) -> None:
        """Prompts user to select a .csv file for processing.

        Opens a tk filedialog to enable file selection, makes sure the file is readable,
        controls enabling/disabling of 'Settings' & 'Process' buttons. Called when user
        clicks 'Browse' button.
        """
        try:
            self.src_path = fd.askopenfilename(title="Select .csv file", filetypes=[("csv", ".csv")])
            path, f = os.path.split(self.src_path)
            _, ext = os.path.splitext(self.src_path)

            # handle file not chosen or wrong filetype chosen
            if not self.src_path:
                raise RuntimeError
            elif ext != ".csv":
                raise TypeError

            # make sure we can open the selected file
            if not CSVProc.test_open(self.src_path):
                self._set_entry_box_message("Unable to open selected file :(", is_error_msg=True)
                self.process_btn.state(["disabled"])
                self.settings_btn.state(["disabled"])
            else:
                # print filename in Entry field next to 'Save' button
                self._set_entry_box_message(f)
                self.settings_btn.state(["!disabled"])
                # get the processor ready to process
                self.processor.src_path = self.src_path
        except RuntimeError:
            self._set_entry_box_message("No file selected")
            self.settings_btn.state(["disabled"])
            self.process_btn.state(["disabled"])
            self.set_progress(0)
        except TypeError:
            self._set_entry_box_message(f"Invalid filetype: {ext}", is_error_msg=True)
            self.settings_btn.state(["disabled"])
            self.process_btn.state(["disabled"])
            self.set_progress(0)
        except:
            self._set_entry_box_message("Unknown error =/", is_error_msg=True)
            self.settings_btn.state(["disabled"])
            self.process_btn.state(["disabled"])
            self.set_progress(0)


    def _set_entry_box_message(self, message: str, is_error_msg: bool = False):
        if is_error_msg:
            self.source_entry['foreground'] = "red"
        else:
            self.source_entry['foreground'] = self.src_entry_default_color

        self.src_entry_var.set(message)


    def get_dest_file(self) -> None:
        """'Process' button click handler.

        Prompts user for a directory for output files & calls CSVProc process() function.
        """
        dest_path = fd.askdirectory(title="Select save location")
        self.processor.dest_path = dest_path
        self.processor.process(progress_callback=self.set_progress, result_callback=self._display_info_message)


    def open_settings(self):
        SettingsWindow(self.window, self.processor, self.src_path, save_success_callback=self.enable_proc_button)


    def enable_proc_button(self):
        self.process_btn.state(["!disabled"])


    def set_progress(self, value, *, increment=False):
        """Sets (or increments) the underlying value of the progressbar (0-100).

        Note, setting progressbar to 100 is visually identical to 0... 99.9 is used here to represent "full".

        Args:
            value: the value to set(/increment) the progressbar to(/by)
            increment: boolean flag to indicate whether param 'value' is interpreted as a new value or an increment amount.
        """
        if increment:
            value += self.curr_prog_var.get()

        if value >= 100.0:
            value = 99.9
        elif value < 0:
            value = 0

        self.curr_prog_var.set(value)


    def shutdown_ttk_repeat(self):
        # this function fixes an error on window close
        self.window.eval('::ttk::CancelRepeat')
        self.window.destroy()


    @staticmethod
    def _display_info_message(msg):
        messagebox.showinfo(message=msg)
