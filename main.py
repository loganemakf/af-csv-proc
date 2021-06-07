# main.py
# af-csv-proc - Post-processor for exported auction catalogs
# Copyright (C) 2021  Logan Foster
#
# Run this file to launch the GUI

import tkinter as tk
from src.GUI.MainWindow import MainWindow
from src.CSVProc.CSVProc import CSVProc


if __name__ == '__main__':
    root = tk.Tk()
    processor = CSVProc()
    app = MainWindow(root, processor)
