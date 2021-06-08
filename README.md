# af-csv-proc

## A post-processor for AuctionFlex-exported catalog files.
***

![af csv proc main window](/screenshots/img/mainwindow_1.0.png?raw=true)
![af csv proc settings window](/screenshots/img/settingswindow_1.0.png?raw=true)

af-csv-proc is a Python program that processes an auction catalog .csv file for upload to third-party bidding 
platforms such as LiveAuctioneers and Invaluable. It attempts to correct a number of issues present in catalog files 
introduced during export from AuctionFlex (including lot descriptions split into 5 fields, fields truncated, etc.) as 
well as issues caused by human error in the cataloging process (including extraneous whitespace, inconsistent 
punctuation, numerical value errors, etc.).

#### Requirements
* Python 3.9+ (may work on earlier versions but that hasn't been tested)
    * The latest release of Python from [python.org](https://www.python.org) is recommended as it also 
      includes the most up-to-date version of Tk.
* As af-exp-csv is built using Python and tkinter, it is cross-platform and should work on macOS, Windows, & Linux.

***
### Getting Started
Clone or download this repo, then run `python3 main.py` in your terminal to launch the GUI.

A sample workflow might look something like the following:
1.  **Export auction from AuctionFlex (Auction Lots & Preview Images > Export).**
    
    If your catalog is complex (or has seldom-used fields), make note of the field export order; you'll use 
      this later to tell af-csv-proc what data each column contains. *Make sure to select "Comma Delimited Text File .
    CSV" in the File Type section of AuctionFlex's export UI.*
2.  **Run af-csv-proc; click "Browse" and select catalog .csv file.**
3.  **Open settings window & label table columns according to their contents.**
4.  **Save settings; click "Process" button to select an output directory.**
    
    Exported catalog files and a warning log will be saved to this directory. An empty directory is recommended as 
    af-csv-proc does not currently have any protection against overwriting existing files.
5.  **After confirming a directory, af-csv-proc will process the catalog file and display a popup indicating 
    success or failure upon completion (usually quite fast).**
6.  **Even if af-csv-proc succeeds, it is critical that the user check the warning log to identify issues not 
    automatically corrected during processing.**
    
    As an example, af-csv-proc checks whether a lot's description ends with either a '.' or ')' character. While the 
    absence of one of these characters is a minor punctuation issue on its own, it can also indicate that a 
    description has been truncated mid-sentence during export from AuctionFlex (which is far more serious).
    
A short sample AuctionFlex catalog file, `catalog_sample.csv`, is provided in the root of this repository.
***
### Background
The process of uploading an auction catalog created in AuctionFlex to a third-party internet bidding platform 
involves an unnecessary extra processing step that potentially introduces further human error into the cataloging 
process. The need to format the same catalog for multiple bidding platforms compounds this issue.

Prior to writing this program, exported catalog files would have to be imported into a spreadsheet program (like 
Excel) then manually manipulated in order to concatenate the 5-way-split description into a single field, replace 
condition reports (often truncated) with standard boilerplate report text, and split alpha-suffix lots (ex: lot 205A) 
into numeric- and alpha-components, among other things. Typically, these changes would be made to conform to the 
catalog requirements of one bidding platform, exported back to a .csv file, then adapted again to the second bidding 
platform's requirements and exported a second time.

Automating these operations saves time at a point in the auction production process when time is in short supply. It 
also enables checks and verification more thorough than any human could reasonably be for a 300+ lot auction catalog.

***
### Construction & Extensibility
The CSVProc class enables modular operations to be performed on catalog data. Each bidding platform has its own 
export function which calls, in sequence, a number of "check" functions which operate on and validate various 
aspects of the lot data. New "checks" can be added relatively easily (though care must be taken regarding call-order as 
check functions are allowed to modify data) and reused by other export functions, if applicable.


***
*"AuctionFlex", "Invaluable", and "LiveAuctioneers" are registered trademarks of their respective owners.*