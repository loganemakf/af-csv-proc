# This is a sample Python script.

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

import tkinter as tk
from src.GUI import MainWindow as MW
from src.csvproc.csvproc import CSVProc



def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press ⌘F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    root = tk.Tk()
    processor = CSVProc()
    app = MW.MainWindow(root, processor)



    print_hi('PyCharm')



# See PyCharm help at https://www.jetbrains.com/help/pycharm/
