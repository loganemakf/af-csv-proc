"""Command-line entry point: `auctionfix process Auction_26.xml -o exports/`."""
import argparse
import json
import sys
from pathlib import Path

from . import CONF
from .labels import LabelOptions, available_layouts


def _process(args: argparse.Namespace) -> int:
    from .processor.xml_proc import XMLProc

    src = Path(args.input)
    if src.suffix.lower() != ".xml":
        print("Only AuctionFlex XML exports can be processed from the command line; use the GUI (main.py) for CSV "
              "exports, whose columns need labelling.", file=sys.stderr)
        return 2
    dest = Path(args.output) if args.output else src.parent
    dest.mkdir(parents=True, exist_ok=True)

    proc = XMLProc()
    proc.src_path, proc.dest_path = src, dest
    settings = json.loads(Path(args.settings).read_text()) if args.settings else {}
    proc.using_bp_condition = settings.get(CONF.USING_BP_COND, False)
    proc.bp_condition = settings.get(CONF.BP_COND, "")
    proc.calc_startbids = True
    proc.calc_empty_startbids = True
    options = LabelOptions(label_footer=args.label_footer, auction_name=args.auction_name,
                           show_estimates=not args.no_estimates)
    proc.process(progress_callback=lambda *a: None, result_callback=print, make_labels=args.labels,
                 label_layout=args.label_layout, label_options=options)
    print(f"Wrote upload files to {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auctionfix", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    process = commands.add_parser("process", help="process an AuctionFlex XML export into platform upload files")
    process.add_argument("input", help="AuctionFlex XML export")
    process.add_argument("-o", "--output", help="folder for the upload files (default: the input's folder)")
    process.add_argument("--settings", help="settings file saved by the GUI (config.json)")
    process.add_argument("--labels", action="store_true", help="also make standard lot labels (PDF)")
    process.add_argument("--label-layout", default="avery5160", help="label layout (see `auctionfix layouts`)")
    process.add_argument("--label-footer", default="", help="footer text for the labels")
    process.add_argument("--auction-name", default="", help="auction name, for layouts that show it")
    process.add_argument("--no-estimates", action="store_true", help="leave estimates off the labels")
    commands.add_parser("layouts", help="list the installed label layouts")
    args = parser.parse_args(argv)
    if args.command == "layouts":
        for key, layout in sorted(available_layouts().items()):
            print(f"{key:20} {layout.name}")
        return 0
    if args.labels and args.label_layout not in available_layouts():
        parser.error(f"unknown label layout {args.label_layout!r}; run `auctionfix layouts`")
    return _process(args)


if __name__ == "__main__":
    sys.exit(main())
