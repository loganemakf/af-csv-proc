# __init__.py (package)
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

# PROGRAM CONSTANTS
class C:
    PROGRAM_NAME = "AF .csv Processor v1.0.0"


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
