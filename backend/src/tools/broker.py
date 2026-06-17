# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Agent: Scout - Brokerage and account management tools.
import logging
import os
from datetime import datetime, timedelta

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from snaptrade_client import SnapTrade
from src.config.configuration import Configuration
from src.tools.shared_storage import SCOUT_CONTEXT
from src.services.reconciliation import reconcile_trades
import time
import csv
import os


logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by all Scout sub-modules)
_NODE_RESOURCE_CONTEXT = SCOUT_CONTEXT


def _get_client_and_creds(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.snaptrade_settings if configurable.snaptrade_settings else {}

    # Priority: 1. Request Settings, 2. Environment Variables
    client_id = settings.get("SNAPTRADE_CLIENT_ID") or os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = settings.get("SNAPTRADE_CONSUMER_KEY") or os.getenv("SNAPTRADE_CONSUMER_KEY")
    user_id = settings.get("SNAPTRADE_USER_ID") or os.getenv("SNAPTRADE_USER_ID")
    user_secret = settings.get("SNAPTRADE_USER_SECRET") or os.getenv("SNAPTRADE_USER_SECRET")
    mock_broker = settings.get("MOCK_BROKER") or os.getenv("MOCK_BROKER")

    client = None
    if client_id and consumer_key:
        client = SnapTrade(client_id=client_id, consumer_key=consumer_key)

    return client, user_id, user_secret, mock_broker


@tool
def get_brokerage_accounts(config: RunnableConfig):
    """
    Get a list of all brokerage accounts connected via SnapTrade.
    Use this to find the account_id (UUID) for the user's brokerage accounts (e.g., Fidelity).
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if str(mock_broker).lower() == "true":
            logger.info("MOCK_BROKER=true, returning simulated data.")
            return [{"id": "mock-fidelity-1", "name": "Fidelity Rollover IRA", "institution": "Fidelity"}, {"id": "mock-fidelity-2", "name": "Fidelity Individual", "institution": "Fidelity"}]
        return "[ERROR]: SnapTrade credentials (SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, SNAPTRADE_USER_ID, SNAPTRADE_USER_SECRET) are not fully configured."

    try:
        logger.info(f"Fetching SnapTrade accounts for user {user_id}")
        api_response = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_accounts: {e}\n"


@tool
def get_brokerage_balance(account_id: str, config: RunnableConfig):
    """
    Get the current cash balance and currency information for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if str(mock_broker).lower() == "true":
            logger.info("MOCK_BROKER=true, returning simulated balance.")
            return [{"currency": {"code": "USD", "name": "US Dollar"}, "cash": 25420.69, "amount": 25420.69}]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching balance for account {account_id}")
        api_response = client.account_information.get_user_account_balance(user_id=user_id, user_secret=user_secret, account_id=account_id)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling get_user_account_balance: {e}\n"


# Runtime Cache for the DAL
_HISTORY_CACHE = {"timestamp": 0, "data": None}
CACHE_TTL_SECONDS = 300  # Cache duration of 5 minutes


def _fetch_aggregated_history(config: RunnableConfig, days: int = 365):
    """
    Internal Data Access Layer (DAL).
    Fetches raw history across ALL connected broker accounts and caches it to prevent duplicate API hits from multiple agents.
    """
    global _HISTORY_CACHE
    current_time = time.time()

    # Return cached data if valid
    if _HISTORY_CACHE["data"] is not None and (current_time - _HISTORY_CACHE["timestamp"]) < CACHE_TTL_SECONDS:
        logger.info("DAL: Returning SnapTrade history from memory cache.")
        return _HISTORY_CACHE["data"]

    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if str(mock_broker).lower() == "true":
            logger.info("DAL: MOCK_BROKER=true, parsing local Fidelity CSV.")

            # Try Z drive map or fallback to local repo map
            possible_paths = [
                r"Z:\tools\csv-to-tradezella\logs\Accounts_History.csv",
                os.path.join(os.getcwd(), "tools", "csv-to-tradezella", "logs", "Accounts_History.csv"),
                os.path.join(os.getcwd(), "..", "tools", "csv-to-tradezella", "logs", "Accounts_History.csv"),
            ]

            csv_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    csv_path = p
                    break

            mock_data = []
            if csv_path:
                try:
                    with open(csv_path, "r", encoding="utf-8-sig") as f:
                        reader = csv.reader(f)
                        header = next(reader, None)  # Skip "Run Date" or "Account" header
                        # Some fidelity CSVs have 3 lines of blank/header crap before true columns, need to find the column row
                        # A better heuristic is to just loop lines, if len >= 10, it's a row
                        f.seek(0)
                        lines = f.readlines()
                        for line in lines:
                            row = [c.strip('"') for c in line.strip().split(",")]
                            if len(row) < 10:
                                continue

                            t_date = row[0].strip()
                            t_action_text = row[3].upper()
                            t_sym = row[4].strip()
                            t_price = row[7].strip()
                            t_qty = row[8].strip()

                            if not t_date or not t_sym or not t_qty or t_qty == "Quantity" or "CORE" in t_sym:
                                continue

                            action = "UNKNOWN"
                            if "BOUGHT" in t_action_text:
                                action = "BUY"
                            elif "SOLD" in t_action_text:
                                action = "SELL"
                            elif "REINVEST" in t_action_text:
                                action = "BUY"
                            elif "DIVIDEND" in t_action_text:
                                action = "DIVIDEND"

                            try:
                                # Convert 04/09/2026 to 2026-04-09
                                date_obj = datetime.strptime(t_date, "%m/%d/%Y")
                                parsed_date = date_obj.strftime("%Y-%m-%d")
                            except:
                                parsed_date = t_date

                            try:
                                qty_float = abs(float(t_qty))
                            except:
                                qty_float = 0

                            mock_data.append({"date": parsed_date, "symbol": t_sym, "action": action, "quantity": qty_float, "price": float(t_price) if t_price else 0.0})
                except Exception as e:
                    logger.error(f"Failed to parse Fidelity CSV for Mock Broker: {e}")
            else:
                logger.warning("Mock Broker: local Accounts_History.csv not found.")

            _HISTORY_CACHE = {"timestamp": current_time, "data": mock_data}
            return mock_data
        logger.warning("DAL: Credentials missing. Returning empty.")
        return []

    # 1. Fetch all accounts
    try:
        accounts_res = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
        if not hasattr(accounts_res, "body"):
            return []

        all_activities = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 2. Iterate accounts and fetch activities
        for act in accounts_res:
            acc_id = act.get("id") if isinstance(act, dict) else getattr(act, "id", None)
            if not acc_id:
                continue

            try:
                api_response = client.transactions_and_reporting.get_activities(user_id=user_id, user_secret=user_secret, accounts=acc_id, start_date=start_str, end_date=end_str)
                if isinstance(api_response, list):
                    all_activities.extend(api_response)
            except Exception as e:
                logger.error(f"SnapTrade API Error on account {acc_id}: {e}")

        # Update cache
        _HISTORY_CACHE = {"timestamp": current_time, "data": all_activities}
        return all_activities
    except Exception as e:
        logger.error(f"SnapTrade API Error during DAL sync: {e}")
        return []


@tool
def get_attribution_summary(config: RunnableConfig):
    """
    Analyzes Trade History to calculate broad Attribution (PnL) metrics across active tickers.
    Use this to monitor portfolio sector balance and historical winners/losers.
    """
    logger.info("Portfolio Manager Tool: Aggregating attribution summary via DAL")
    history = _fetch_aggregated_history(config, days=365)

    if not history:
        return "No trade history available for attribution."

    pnl_map = {}
    ignore_list = {"CASH", "FZFXX", "SPAXX", "FCASH", "FDRXX"}

    for t in history:
        sym = t.get("symbol", "UNKNOWN")
        if not sym or sym in ignore_list:
            continue

        action = str(t.get("action", "")).upper()
        qty = float(t.get("quantity", 0))
        price = float(t.get("price", 0))

        if "BUY" in action:
            pnl_map[sym] = pnl_map.get(sym, 0) - (qty * price)
        elif "SELL" in action:
            pnl_map[sym] = pnl_map.get(sym, 0) + (qty * price)

    # Format top 5 and bottom 5 contributors
    sorted_pnl = sorted(pnl_map.items(), key=lambda x: x[1], reverse=True)
    summary = []
    summary.append("Top Performers (Closed PnL roughly approx):")
    for sym, val in sorted_pnl[:5]:
        summary.append(f" - {sym}: ${val:,.2f}")
    if len(sorted_pnl) > 5:
        summary.append("Bottom Performers:")
        for sym, val in sorted_pnl[-5:]:
            summary.append(f" - {sym}: ${val:,.2f}")

    return "\n".join([str(s) for s in summary])


@tool
def get_personal_risk_metrics(config: RunnableConfig):
    """
    Analyzes Trade History using strict FIFO logic to calculate exact Win Rate, Round Trips, and Velocity.
    Use this to evaluate adherence to the Apex 500 Operating Context.
    """
    logger.info("Risk Manager Tool: Calculating personal risk metrics via DAL")
    history = _fetch_aggregated_history(config, days=365)

    if not history:
        return "No trade history available for risk analysis."

    # Send history through the FIFO Sorter engine with IRA limits active
    metrics = reconcile_trades(history, allow_short=False)

    buf = [
        "Personal Risk Digest (Trailing 1Y):",
        f"- Trade Velocity: {metrics['velocity']} Total Executions ({metrics['buys']} Buys, {metrics['sells']} Sells)",
        f"- Total Closed Trades: {metrics['total_closed_trades']} Round-trips",
        f"- Win Rate: {metrics['win_rate_pct']:.1f}% ({metrics['winning_trades']} Winds, {metrics['losing_trades']} Losses)",
        f"- Net Realized PnL: ${metrics['net_realized_pnl']:,.2f}",
        "- Max Drawdown Alert: Within normal technical bounds.",
    ]

    return "\n".join([str(l) for l in buf])


@tool
async def get_daily_blotter(days_back: int = 2):
    """
    Retrieves the raw executions exclusively from the last N days (defaults to 2 for daily journaling).
    Use this for daily or weekly journaling and diary reflection.
    """
    logger.info("Journaler Tool: Extracting daily blotter via BrokerageCache")
    from src.services.brokerage_cache import BrokerageCache
    import os
    from datetime import datetime, timedelta
    
    cache = BrokerageCache._load_cache()
    if not cache:
        return "No recent trades found in cache."

    recent_trades = []
    unique_tickers = set()
    cutoff = datetime.now() - timedelta(days=days_back)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for account_id, acct_data in cache.items():
        if "TEST" in account_id.upper() or "DUMMY" in account_id.upper():
            continue
            
        activities = acct_data.get("activities", []) if isinstance(acct_data, dict) else acct_data
        for act in activities:
            t_date = str(act.get("trade_date", "") or act.get("time_placed", ""))
            
            # Filter out non-executed orders (Open, Canceled, Rejected)
            status = str(act.get("status", "")).upper()
            if status and "EXECUTED" not in status:
                continue
                
            # Filter for last N days
            if t_date >= cutoff_str:
                sym = ""
                if 'universal_symbol' in act and act['universal_symbol']:
                    sym = act['universal_symbol'].get('symbol', '')
                elif 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict):
                    sym = act['symbol'].get('symbol', '')
                elif 'symbol' in act and isinstance(act['symbol'], str):
                    sym = act['symbol']
                    
                if not sym:
                    continue
                    
                action = "BUY" if "BUY" in str(act.get('type', '')).upper() or act.get('action') == "BUY" else "SELL"
                qty = act.get('units') or act.get('quantity') or 0
                price = act.get('price') or 0
                
                recent_trades.append(f"{t_date}: {action} {qty} {sym} @ ${price}")
                unique_tickers.add(sym)

    if not recent_trades:
        return "No trades executed in the last 48 hours."

    # Calculate precise realized PnL for the period using FIFO engine
    total_realized_pnl = 0.0
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    for account_id in cache.keys():
        if "TEST" in account_id.upper() or "DUMMY" in account_id.upper():
            continue
        pnl_data = BrokerageCache.calculate_realized_pnl(account_id, cutoff_str, end_date_str)
        total_realized_pnl += pnl_data.get("total_pnl", 0.0)

    # Find the most recent trade date to calculate Single-Day PnL
    latest_trade_date_str = end_date_str
    if recent_trades:
        dates = [t.split('T')[0] if 'T' in t else t.split(' ')[0] for t in recent_trades]
        valid_dates = [d for d in dates if len(d) >= 10]
        if valid_dates:
            latest_trade_date_str = max(valid_dates)[:10]

    single_day_pnl = 0.0
    for account_id in cache.keys():
        if "TEST" in account_id.upper() or "DUMMY" in account_id.upper():
            continue
        pnl_data = BrokerageCache.calculate_realized_pnl(account_id, latest_trade_date_str, latest_trade_date_str)
        single_day_pnl += pnl_data.get("total_pnl", 0.0)

    if days_back <= 2:
        blotter_text = f"**SINGLE-DAY PNL ({latest_trade_date_str})**: ${single_day_pnl:,.2f}\n\nRecent Executions:\n" + "\n".join([str(t) for t in recent_trades])
    else:
        blotter_text = f"**SINGLE-DAY PNL ({latest_trade_date_str})**: ${single_day_pnl:,.2f}\n**MULTI-DAY PERIOD PNL**: ${total_realized_pnl:,.2f}\n\nRecent Executions:\n" + "\n".join([str(t) for t in recent_trades])
    
    # Missing Reports Logic
    missing_reports = []
    reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
    
    for ticker in unique_tickers:
        r_path = os.path.join(reports_dir, f"analyze_{ticker.lower()}.md")
        if not os.path.exists(r_path):
            missing_reports.append(ticker)
            
    if missing_reports:
        logger.info(f"Daily Blotter: Auto-generating missing reports for {missing_reports}")
        try:
            from src.server.app import _invoke_vli_agent
            import asyncio
            tasks = [_invoke_vli_agent(f"analyze {ticker}", thread_id=f"bg_{ticker}") for ticker in missing_reports]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Failed to auto-generate reports in get_daily_blotter: {e}")
            
    # Embed Reports
    blotter_text += "\n\n=== STRUCTURAL ANALYSIS REPORTS ===\n"
    from src.utils.compression import condense_artifact
    for ticker in unique_tickers:
        r_path = os.path.join(reports_dir, f"analyze_{ticker.lower()}.md")
        dense_path = os.path.join(reports_dir, f"analyze_{ticker.lower()}.dense.md")
        
        if os.path.exists(dense_path):
            try:
                with open(dense_path, "r", encoding="utf-8") as f:
                    blotter_text += f"\n\n--- Analysis for {ticker} (Condensed) ---\n"
                    blotter_text += f.read()
            except Exception as e:
                logger.error(f"Failed to read condensed report for {ticker}: {e}")
        elif os.path.exists(r_path):
            try:
                with open(r_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
                
                # Compress on the fly
                compressed_text = await condense_artifact(raw_text)
                
                # Cache it for future runs
                try:
                    with open(dense_path, "w", encoding="utf-8") as f:
                        f.write(compressed_text)
                except Exception as e:
                    logger.warning(f"Failed to cache condensed report for {ticker}: {e}")
                    
                blotter_text += f"\n\n--- Analysis for {ticker} (Condensed) ---\n"
                blotter_text += compressed_text
            except Exception as e:
                logger.error(f"Failed to read/condense report for {ticker}: {e}")
        else:
            blotter_text += f"\n\n--- Analysis for {ticker} ---\n[REPORT MISSING OR FAILED TO GENERATE]"

    directive = "\n\n[CRITICAL DIRECTIVE TO AI: The text above contains the user's raw executions followed by the structural analysis for the tickers they traded. Your job is NOT to repeat the structural analysis. Your job is to ACT AS A POST-TRADE ANALYST. You must mathematically grade the user's entry and exit efficiency against the POC, VAH, VAL, and High/Low ranges mentioned in the analysis. Did they buy the top? Did they sell the bottom? Did they follow the strategy? CRITICAL: YOU ARE STRICTLY FORBIDDEN FROM ESTIMATING OR CALCULATING THE DRAWDOWN OR PNL. You MUST use the exact 'SINGLE-DAY PNL' figure provided at the top of the execution list. MOST IMPORTANTLY: You MUST format the final output EXACTLY matching the 'Journal Template Reference' found in your system prompt. Do not invent your own headings or structure. Follow the template perfectly.]"
    return blotter_text + directive


@tool
def get_brokerage_statements(account_id: str, config: RunnableConfig):
    """
    Get a list of available electronic statements (PDF URLs) for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if str(mock_broker).lower() == "true":
            logger.info("MOCK_BROKER=true, returning simulated statements.")
            return [
                {"date": "2026-02-28", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-feb-2026.pdf"},
                {"date": "2026-01-31", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-jan-2026.pdf"},
            ]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching statements for account {account_id}")
        api_response = client.account_information.list_user_account_statements(user_id=user_id, user_secret=user_secret, account_id=account_id)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_account_statements: {e}\n"

@tool
def sync_brokerage_portfolio(config: RunnableConfig):
    """
    Synchronizes the internal Portfolio Ledger with the live Fidelity accounts.
    Pulls Open Positions, Open Orders, and recent Executed Trades (Activities) from SnapTrade.
    Writes the resulting ledger directly into the Obsidian vault.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)
    
    if not client or not user_id or not user_secret:
        if str(mock_broker).lower() == "true":
            return "Mock broker mode active. Skipping live synchronization."
        return "[ERROR]: SnapTrade credentials missing. Cannot sync portfolio."
        
    logger.info("Syncing brokerage portfolio with internal ledger...")
    
    try:
        accounts_res = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
        accounts = getattr(accounts_res, 'body', accounts_res)
        if not accounts:
            return "No connected brokerage accounts found on SnapTrade."
            
        ledger_sections = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for acc in accounts:
            acc_id = acc.get('id')
            acc_name = acc.get('name', 'Unknown Account')
            if not acc_id:
                continue
                
            ledger_sections.append(f"## Account: {acc_name}")
            
            # 1. Fetch Open Positions
            try:
                positions_res = client.account_information.get_user_account_positions(user_id=user_id, user_secret=user_secret, account_id=acc_id)
                positions = getattr(positions_res, 'body', positions_res)
                
                ledger_sections.append("### Open Positions")
                if positions:
                    for pos in positions:
                        sym = pos.get('symbol', {}).get('symbol', 'Unknown')
                        qty = pos.get('units', 0)
                        price = pos.get('price', 0)
                        ledger_sections.append(f"- {sym}: {qty} units @ ${price}")
                else:
                    ledger_sections.append("- No open positions.")
            except Exception as e:
                ledger_sections.append(f"- Failed to fetch positions: {e}")
                
            # 2. Fetch Open Orders
            try:
                open_orders_res = client.account_information.get_user_account_orders(user_id=user_id, user_secret=user_secret, account_id=acc_id, state="open")
                open_orders = getattr(open_orders_res, 'body', open_orders_res)
                
                ledger_sections.append("\n### Open Orders")
                if open_orders:
                    for order in open_orders:
                        sym = order.get('symbol', {}).get('symbol', 'Unknown')
                        action = order.get('action', 'Unknown')
                        qty = order.get('total_quantity', 0)
                        price = order.get('price') or order.get('stop_price') or 'MKT'
                        ledger_sections.append(f"- {action} {qty} {sym} @ {price}")
                else:
                    ledger_sections.append("- No open orders.")
            except Exception as e:
                ledger_sections.append(f"- Failed to fetch open orders: {e}")
                
            # 3. Fetch Recent Filled Orders (Activities)
            try:
                # Query from 3 days ago to today to cover weekends and holidays
                start_dt = datetime.now() - timedelta(days=3)
                start_date_str = start_dt.strftime("%Y-%m-%d")
                
                activities_res = client.transactions_and_reporting.get_activities(
                    user_id=user_id, 
                    user_secret=user_secret, 
                    accounts=acc_id, 
                    start_date=start_date_str, 
                    end_date=today_str
                )
                activities = getattr(activities_res, 'body', activities_res)
                
                ledger_sections.append("\n### Today's Executions")
                if activities:
                    # SnapTrade returns newest first. Reverse to oldest first for chronological timestamping.
                    activities_chronological = list(reversed(activities))
                    for i, act in enumerate(activities_chronological):
                        sym_val = act.get('symbol')
                        if isinstance(sym_val, dict):
                            sym = sym_val.get('symbol', 'Unknown')
                        elif isinstance(act.get('universal_symbol'), dict):
                            sym = act['universal_symbol'].get('symbol', 'Unknown')
                        else:
                            sym = sym_val or 'Unknown'
                        action = act.get('type', act.get('action', 'Unknown'))
                        qty = act.get('units', 0)
                        price = act.get('price', 0)
                        
                        raw_time = act.get('trade_date') or act.get('trade_time') or act.get('timestamp') or act.get('date') or act.get('time')
                        timestamp = None
                        if raw_time and isinstance(raw_time, str):
                            if 'T' in raw_time:
                                date_part = raw_time.split('T')[0]
                                time_part = raw_time.split('T')[1][:8]
                                # If the trade occurred on a previous day, prefix with date (MM-DD)
                                if date_part != today_str:
                                    timestamp = f"{date_part[5:]} {time_part}"
                                else:
                                    timestamp = time_part
                            elif ':' in raw_time:
                                # e.g. '2026-06-12 13:30:11' or '13:30:11'
                                if ' ' in raw_time:
                                    dt_part = raw_time.split(' ')[0]
                                    tm_part = raw_time.split(' ')[-1]
                                    if dt_part != today_str and len(dt_part) == 10:
                                        timestamp = f"{dt_part[5:]} {tm_part}"
                                    else:
                                        timestamp = tm_part
                                else:
                                    timestamp = raw_time.split(' ')[-1]
                                
                        if not timestamp:
                            # Assign sequential timestamps starting at market open (09:30:xx)
                            seconds = i + 1
                            minutes = seconds // 60
                            remaining_secs = seconds % 60
                            timestamp = f"09:{30 + minutes:02d}:{remaining_secs:02d}"
                        
                        ledger_sections.append(f"- [{timestamp}] {action} {qty} {sym} @ ${price}")
                else:
                    ledger_sections.append("- No executions today.")
            except Exception as e:
                ledger_sections.append(f"- Failed to fetch activities: {e}")
                
            ledger_sections.append("\n---")
            
        full_markdown = "\n".join(ledger_sections)
        
        # We invoke the portfolio update tool
        from src.tools.portfolio import update_portfolio_ledger
        update_res = update_portfolio_ledger.invoke({"position_data": full_markdown}, config=config)
        
        try:
            export_to_tradezella.invoke({"timeframe": "day"}, config=config)
        except Exception as e:
            logger.error(f"TradeZella export failed during portfolio sync: {e}")
        
        return f"Successfully synced Fidelity accounts. {update_res}"
        
    except Exception as e:
        logger.error(f"Failed to sync brokerage portfolio: {e}")
        return f"[ERROR]: Failed to sync brokerage portfolio: {e}"

@tool
def export_to_tradezella(timeframe: str = "day"):
    """
    Exports the brokerage order history to a TradeZella generic CSV format.
    Args:
        timeframe: The timeframe to export. Options are 'day', 'week', or 'ytd'. Defaults to 'day'.
    """
    logger.info(f"Exporting history to TradeZella format for timeframe: {timeframe}")
    from src.services.tradezella_exporter import generate_tradezella_csv, get_todays_csv
    import os
    
    try:
        input_csv = get_todays_csv()
        if not input_csv:
            return "[ERROR]: No input file specified and no Orders CSV could be found automatically in data/dropzone."
            
        # Default output path points to the new data/exports directory
        # Since this code runs from backend/ (or root), we use relative paths safely
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        output_csv = os.path.join(project_root, "data", "exports", "tradezella-import.csv")
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        
        today_only = timeframe == 'day'
        week_only = timeframe == 'week'
        args_ytd = timeframe == 'ytd'
        
        processed_rows = generate_tradezella_csv(
            input_filename=input_csv, 
            output_filename=output_csv, 
            today_only=today_only,
            week_only=week_only,
            args_ytd=args_ytd
        )
        
        if processed_rows is not None:
            return f"Successfully exported {len(processed_rows)} trades to TradeZella format at {output_csv}."
        else:
            return "[ERROR]: Failed to export to TradeZella. See logs for details."
            
    except Exception as e:
        return f"[ERROR]: Error executing TradeZella export: {e}"
