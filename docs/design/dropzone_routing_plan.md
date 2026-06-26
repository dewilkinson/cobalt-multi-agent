# Implementation Plan - Dynamic Dropzone File Routing & Type Recognition

This plan details the changes required to:
1. Add central dropzone routing configuration in `conf.yaml`.
2. Match files in the dropzone folder using regex patterns defined in `DROPZONE_ACCOUNTS` to trace the exporting tool/account.
3. Intelligently select the correct parser/importer based on the matched tool/account:
   - For `"TradingView Paper Trading"`, use the TradingView paper trading importer.
   - For Fidelity accounts (e.g. `"Rollover IRA *5513"`, `"Health Savings Account *6937"`), determine the Fidelity sub-type (`orders`, `history`, `positions`, `closed_positions`) from the filename and use the corresponding Fidelity parser.
4. Rename `atp_importer.py` to `csv_importer.py` and rename its internal Fidelity parsers to replace `_atp_` with `_fidelity_` (e.g. `parse_fidelity_orders`).
5. Maintain backwards-compatible legacy stubs (`atp_importer.py` importing from `csv_importer.py` and legacy aliases) to prevent breaking legacy scripts.
6. Skip and leave unprocessed/un-archived any files that are not matched or recognized.
7. Implement unit tests verifying the routing and exclusion behavior.

## Proposed Changes

### 1. Central Configuration (`conf.yaml`)

#### [MODIFY] [conf.yaml](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/conf.yaml)

- Append the daily established regex for the Rollover IRA account and HSA:
  ```yaml
  DROPZONE_ACCOUNTS:
    "Rollover IRA *5513": ".*Rollover_IRA__5513.*\\.csv"
    "Health Savings Account *6937": ".*Health_Savings.*\\.csv"
    "TradingView Paper Trading": ".*paper-trading-order-history.*\\.csv"
  ```

---

### 2. Backend Service Layer (`csv_importer.py`)

#### [NEW] [csv_importer.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/services/csv_importer.py)

- Create by renaming `atp_importer.py` to `csv_importer.py`.
- Rename functions:
  - `parse_atp_orders` -> `parse_fidelity_orders`
  - `parse_atp_history` -> `parse_fidelity_history`
  - `parse_atp_positions` -> `parse_fidelity_positions`
  - `parse_atp_closed_positions` -> `parse_fidelity_closed_positions`
- Define backwards-compatible legacy aliases at the bottom of the file:
  ```python
  parse_atp_orders = parse_fidelity_orders
  parse_atp_history = parse_fidelity_history
  parse_atp_positions = parse_fidelity_positions
  parse_atp_closed_positions = parse_fidelity_closed_positions
  ```
- Update `process_dropzone_files` to load `DROPZONE_ACCOUNTS` configuration via `get_config()`.
- Scan all `.csv` files in the dropzone folder.
- **Trace Exporting Tool**: For each CSV file, find the matching pattern in `DROPZONE_ACCOUNTS` to determine its target account/source.
- **Determine Importer/Parser**:
  - If the matched target account is `"TradingView Paper Trading"`, select the TradingView parser (`parse_tradingview_paper_trading`).
  - If the matched target account is a Fidelity account:
    - Inspect the filename to identify the specific export type:
      - Contains `"closed"` and `"positions"` -> use `parse_fidelity_closed_positions`.
      - Contains `"positions"` (without `"closed"`) -> use `parse_fidelity_positions`.
      - Contains `"orders"` -> use `parse_fidelity_orders`.
      - Contains `"history"` or `"activity"` -> use `parse_fidelity_history`.
      - If none of these match, the file is not recognized (skip processing).
- **Strict Filtering**: If a file does not match any pattern in `DROPZONE_ACCOUNTS` or does not match a recognized export type, do NOT process or archive it. Leave it intact in the dropzone folder.
- **Account Routing**: Override the target account key in parsed output to the matched key (e.g. `"Rollover IRA *5513"`).
- Run downstream TradeZella and TradingView script generation routines when any updates are made.

#### [NEW] [atp_importer.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/services/atp_importer.py)

- Keep a backwards-compatible stub file containing:
  ```python
  from src.services.csv_importer import *
  ```

#### [MODIFY] [app.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/server/app.py)

- Update imports from `src.services.atp_importer` to `src.services.csv_importer`.

---

### 3. Automated Tests (`test_csv_importer.py`)

#### [NEW] [test_csv_importer.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/tests/unit/test_csv_importer.py)

- Create by renaming `test_atp_importer.py` to `test_csv_importer.py`.
- Update imports to use `src.services.csv_importer`.
- Write `test_process_dropzone_unrecognized_file_ignored` to check that unrecognized CSV files (e.g. `test-file.csv` or `Orders_Unknown_IRA.csv`) are ignored and left in the dropzone, while recognized files are processed and moved.
- Write `test_process_dropzone_regex_routing` to check that files matching `DROPZONE_ACCOUNTS` regexes are correctly mapped and merged to their target accounts in the brokerage cache.

#### [DELETE] [test_atp_importer.py](file:///c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/tests/unit/test_atp_importer.py)

- Delete legacy test file.

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/unit/test_csv_importer.py` before changes to verify failing tests (Red Phase).
- Run `pytest backend/tests/unit/test_csv_importer.py` after changes to verify passing tests (Green Phase).

### Manual Verification
- Drop a mock `Activity_Rollover_IRA__5513.csv` and an unrecognized CSV into `data/dropzone/`.
- Call dropzone processing and verify the unrecognized file remains in the folder, and the activities are successfully merged to `"Rollover IRA *5513"` in `brokerage_cache.json`.
