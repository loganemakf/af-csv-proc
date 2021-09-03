# main.py
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
#
# Run this file ("python3 main.py") to launch the GUI

import tkinter as tk
from src.GUI.MainWindow import MainWindow
from src.CSVProc.CSVProc import CSVProc


if __name__ == '__main__':
    root = tk.Tk()
    processor = CSVProc()
    app = MainWindow(root, processor)
