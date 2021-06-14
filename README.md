### (This branch reserved for screenshots only)
***
# af-csv-proc

## A post-processor for AuctionFlex-exported catalog files.
***

af-csv-proc is a Python program that processes an auction catalog .csv file for upload to third-party bidding 
platforms such as LiveAuctioneers and Invaluable. It attempts to correct a number of issues present in catalog files 
introduced during export from AuctionFlex (including lot descriptions split into 5 fields, fields truncated, etc.) as 
well as issues caused by human error in the cataloging process (including extraneous whitespace, inconsistent 
punctuation, numerical value errors, etc.).

***
*"AuctionFlex", "Invaluable", and "LiveAuctioneers" are registered trademarks of their respective owners.*