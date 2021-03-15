"""
Run this file to launch CSV Processor program.
"""

import tkinter as tk
from src.GUI import MainWindow as MW
from src.csvproc.csvproc import CSVProc


if __name__ == '__main__':
    root = tk.Tk()
    processor = CSVProc()
    app = MW.MainWindow(root, processor)
