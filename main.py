# main.py
# AuctionFix - post-processor for exported auction catalogs
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
from auctionfix.gui.MainWindow import MainWindow
from auctionfix.processor.csv_proc import CSVProc

if __name__ == "__main__":
    af_file_headers = [
        "LotNum",
        "Title",
        "Desc. 1",
        "Desc. 2",
        "Desc. 3",
        "Desc. 4",
        "Desc. 5",
        "Qty",
        "LoEst",
        "HiEst",
        "StartBid",
        "Reserve",
        "Condition",
        "Consign#",
        "[Ignore]",
        "[Ignore]",
        "[Ignore]",
        "Ref#",
        "Height",
        "Width",
        "Depth",
        "DimUnit",
        "Weight",
        "WtUnit",
        "Inv#",
    ]

    root = tk.Tk()
    processor = CSVProc()
    processor.file_headers = af_file_headers
    app = MainWindow(root, processor)
