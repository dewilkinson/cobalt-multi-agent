import os
import sys
import argparse

# Add backend to path to import backend services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))
from src.services.tradezella_exporter import generate_tradezella_csv, launch_audit_dashboard, get_todays_csv

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Fidelity CSV to TradeZella generic format.")
    parser.add_argument("-i", "--input", help="Explicit path to the source CSV file", default=None)
    
    # Default output path points to the new data/exports directory
    default_output = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "exports", "tradezella-import.csv"))
    parser.add_argument("-o", "--output", help="Explicit path for the generated output CSV", default=default_output)
    
    parser.add_argument("-m", "--month", help="Filter trades for a specific calendar month (1-12)", type=int, default=None)
    parser.add_argument("-w", "--week", help="Filter trades to include only the current calendar week", action="store_true")
    parser.add_argument("-d", "--day", help="Filter trades to include only today's executions", action="store_true")
    parser.add_argument("--ytd", help="Filter trades to include only Year-To-Date executions", action="store_true")
    parser.add_argument("--range", help="Filter trades for a custom range, e.g. --range 2026-03-30 2026-04-09", nargs=2, metavar=('START', 'END'))
    parser.add_argument("--reconcile", help="Automatically look back into history to resolve orphaned trades in a date range", action="store_true")
    parser.add_argument("--intraday-only", help="Filter out any interday trades (symbols that do not flatline to 0 locally on a given date)", action="store_true")
    parser.add_argument("--no-audit", help="Disable the automatic HTML audit dashboard launch", action="store_false", dest="audit", default=True)
    args = parser.parse_args()

    input_csv = args.input
    if not input_csv:
        input_csv = get_todays_csv()
        if not input_csv:
            print("Error: No input file specified and no CSV created today was found automatically in data/dropzone.")
            print("Please specify a file using --input <filename>")
            sys.exit(1)
        print(f"Auto-detected today's CSV: {input_csv}")

    output_csv = args.output
    # Ensure the exports folder exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    processed_rows = generate_tradezella_csv(input_csv, output_csv, target_month=args.month, intraday_only=args.intraday_only, week_only=args.week, today_only=args.day, date_range=args.range, reconcile=args.reconcile, args_ytd=args.ytd)
    
    if args.audit and processed_rows:
        launch_audit_dashboard(processed_rows)
