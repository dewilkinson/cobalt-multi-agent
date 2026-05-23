import os

path = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\tools\shield_scanner_trawl.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_import = "from src.tools.scanner import _get_strategy_config"
new_import = "from src.tools.scanner import _get_strategy_config, batch_fetch_sortino"
content = content.replace(old_import, new_import)

# 2. Add sortino block and update verify_candidate to accept the sortino_map
old_vrf = """    # 2. Stage 2: Verification Loop
    logger.info(f"Running Fundamental Verification (SHIELD Defense)...")
    verified_list = []
    sem = asyncio.Semaphore(5) # Throttle fundamental lookups
    
    async def verify_candidate(c):"""

new_vrf = """    # 2. Long-Range Sortino Filtration
    logger.info("Executing 1-Year Long-Range Sortino Floor Check...")
    all_symbols = [c["symbol"] for c in candidates]
    sortino_map = await batch_fetch_sortino(all_symbols, period='1y')

    # 3. Stage 3: Verification Loop
    logger.info(f"Running Fundamental Verification (SHIELD Defense)...")
    verified_list = []
    sem = asyncio.Semaphore(5)  # Throttle fundamental lookups
    
    async def verify_candidate(c):"""
content = content.replace(old_vrf, new_vrf)

old_check = """                # Check Pillar 1 Constraints for Shields
                if beta > 0.4:  # Defensive validation
                    return None
                if div_yield < 0.04: # Minimum 4% true yield
                    return None"""

new_check = """                # Pull 1y Sortino
                c_sortino = sortino_map.get(ticker, 0.0)

                # Check Pillar 1 Constraints for Shields
                if beta > 0.4:  # Defensive validation
                    return None
                if div_yield < 0.04: # Minimum 4% true yield
                    return None
                if c_sortino < 0.0: # Long-range Sortino Floor (No bleeding yields)
                    logger.info(f"Rejected {ticker} - Failed Long-Range Sortino Floor ({c_sortino})")
                    return None"""
content = content.replace(old_check, new_check)


with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected 1-Year Sortino Floor.")
