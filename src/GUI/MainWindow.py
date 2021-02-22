from tkinter import *
from tkinter import ttk
from tkinter import filedialog as fd
import os.path

from src.GUI.SettingsWindow import SettingsWindow
from src.csvproc.csvproc import CSVProc


class MainWindow:

    def __init__(self, root: Tk, processor: CSVProc):
        self.processor = processor
        self.window = root
        self.window.title("Auction .csv Processor GUI v0.1")
        self.window.resizable(FALSE, FALSE)

        self.mainframe = ttk.Frame(self.window, padding="30 15")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        self.lbl_instruct = ttk.Label(self.mainframe, text="Select an AuctionFlex-exported .csv file to process", anchor="center")
        self.lbl_instruct.grid(column=0, row=0, columnspan=3)

        self.src_entry_text = StringVar()
        self.src_path = ""
        self.src_entry_text.set("No file selected")
        self.source_entry = ttk.Entry(self.mainframe, width=30, state="readonly", justify="center",
                                      textvariable=self.src_entry_text)
        self.source_entry.grid(column=0, row=1, columnspan=2, sticky=(W, E))
        self.src_entry_default_color = self.source_entry.cget("foreground")

        self.src_button = ttk.Button(self.mainframe, text="Browse", command=self.get_source_file).grid(column=2, row=1, sticky=W)

        self.step2_frame = ttk.Frame(self.mainframe, padding=5)
        self.step2_frame.grid(column=0, row=2, columnspan=3, sticky=(E,W))
        self.step2_frame.columnconfigure(0, weight=1)
        self.step2_frame.columnconfigure(1, weight=1)
        self.step2_frame.columnconfigure(2, weight=1)
        self.step2_frame.columnconfigure(3, weight=1)
        self.step2_frame.columnconfigure(4, weight=1)
        self.step2_frame.rowconfigure(0, weight=1)

        self.sett_button = ttk.Button(self.step2_frame, text="Settings", state=["disabled"],
                                      command=self.opensettings)
        self.sett_button.grid(column=1, row=0, sticky=E)
        self.dest_path = ""
        self.dest_button = ttk.Button(self.step2_frame, text="Process", state=["disabled"], command=self.getdestfile)
        self.dest_button.grid(column=3, row=0, sticky=W)

        # progBar has 100 steps by default; update with currProg.set(val)
        self.curr_prog = DoubleVar()
        self.prog_bar = ttk.Progressbar(self.mainframe, variable=self.curr_prog, orient=HORIZONTAL, mode="determinate")
        self.prog_bar.grid(column=0, row=3, columnspan=3, sticky=(W, E))

        # add some padding around each UI element in mainframe
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.window.protocol("WM_DELETE_WINDOW", self.shutdown_ttk_repeat)
        self.window.mainloop()


    def get_source_file(self) -> None:
        """Prompts user to select a .csv file for processing.

        Opens a tk filedialog to enable file selection.
        """
        try:
            self.src_path = fd.askopenfilename()
            path, f = os.path.split(self.src_path)
            _, ext = os.path.splitext(self.src_path)

            # handle file not chosen or wrong filetype chosen
            if not self.src_path:
                raise RuntimeError
            elif ext != ".csv":
                raise TypeError

            # make sure we can open the selected file
            if not CSVProc.test_open(self.src_path):
                self._entry_box_message("Unable to open selected file :(")
                self.dest_button.state(["disabled"])
                self.sett_button.state(["disabled"])
            else:
                # print filename in Entry field next to 'Save' button
                self._entry_box_message(f)
                self.dest_button.state(["!disabled"])
                self.sett_button.state(["!disabled"])
        except RuntimeError:
            self._entry_box_message("No file selected")
            self.sett_button.state(["disabled"])
            self.dest_button.state(["disabled"])
        except TypeError:
            self._entry_box_message(f"Invalid filetype: {ext}", is_error_msg=True)
            self.sett_button.state(["disabled"])
            self.dest_button.state(["disabled"])
        except:
            self._entry_box_message("Unknown error =/")
            self.sett_button.state(["disabled"])
            self.dest_button.state(["disabled"])
            pass


    def _entry_box_message(self, message: str, is_error_msg: bool = False):
        if is_error_msg:
            self.source_entry['foreground'] = "red"
        else:
            self.source_entry['foreground'] = self.src_entry_default_color

        self.src_entry_text.set(message)


    def getdestfile(self):
        try:
            dest_path = fd.asksaveasfilename()
            self.curr_prog.set(99.9)
        except:
            dest_path = None

        return dest_path


    def opensettings(self):
        SettingsWindow(self.window, self.processor, self.src_path)


    #TODO: figure out why this doesn't fix the error mssgs on application quit
    def shutdown_ttk_repeat(self):
        self.window.eval('::ttk::CancelRepeat')
        self.window.destroy()
