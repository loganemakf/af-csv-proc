# __init__.py (package)
# af-csv-proc - Post-processor for exported auction catalogs
# Copyright (C) 2021  Logan Foster
#

# PROGRAM CONSTANTS
class C:
    PROGRAM_NAME = "AF .csv Processor v1.0"


# Config file dictionary keys
class CONF:
    BP_COND = "bp_condition"
    USING_BP_COND = "using_bp_condition"
    CALC_STARTBID = "calculate_startbid"
    CALC_EMPTY_STARTBIDS = "calculate_empty_startbids_only"


def try_pass(func):
    def wrapper(*args):
        try:
            func(*args)
        except KeyError:
            pass

    return wrapper
