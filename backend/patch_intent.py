import os

path = r'c:\github\cobalt-multi-agent\backend\src\server\app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the exact target block
target = """    # [FAST-PATH] Shorthand Directive Bypass (Pre-Orchestration)
    # Detects common patterns like "get aapl price", "price of nvda", etc.
    import re
    cleaned_input = request.text.strip().upper()
    ticker = None
    fp_intent = None
    
    # 1. Ticker price variants (AAPL price, get $BTC, price of ETH, etc.)
    # [ULTRA-ROBUST] Catches tickers up to 20 chars with A-Z, 0-9, dots, hyphens, and underscores.
    m = re.search(r"^(?:GET\s+|PRICE\s+OF\s+)?\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$", cleaned_input)
    
    if m:
        ticker = m.group(1)
        fp_intent = "Bypass-Matched"
        
    if ticker and not request.raw_data_mode:"""

# Since I may not have the string exactly matched (because I already ran a string replace on line 1788 earlier, I need to match carefully)
# The string in the file right now literally has `r"^(?:GET\s+|PRICE\s+OF\s+)?\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$"`
# Let's write the replacement explicitly.
replacement = """    # [FAST-PATH] Shorthand Directive Bypass (Pre-Orchestration)
    import re
    cleaned_input = request.text.strip().upper()
    
    # --- HOLISTIC INTENT CLASSIFICATION ---
    QUERY_TOKENS = ["WHY", "WHAT", "HOW", "WHEN", "WHERE", "WHO", "CAN", "SHOULD", "IS", "ARE", "DID", "DO", "DOES", "EXPLAIN", "COMPARE", "ANALYZE"]
    ADMIN_TOKENS = ["CLEAR", "RESET", "REBOOT", "START", "STOP", "PAUSE", "TOGGLE", "PURGE", "FLUSH", "RUN", "GENERATE"]
    
    first_word = cleaned_input.split()[0] if cleaned_input else ""
    
    global_intent = "COMMAND"
    if first_word in QUERY_TOKENS:
        global_intent = "QUERY"
    elif first_word in ADMIN_TOKENS:
        global_intent = "ADMIN"
        
    logger.info(f"VLI Intent Router: Input classified as [{global_intent}]")

    ticker = None
    fp_intent = None
    
    # Only allow Bypass evaluating if the intent is natively COMMAND
    if global_intent == "COMMAND":
        # 1. Ticker price variants (AAPL price, get $BTC, price of ETH, etc.)
        m = re.search(r"^(?:GET\s+|PRICE\s+OF\s+)?\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$", cleaned_input)
        if m:
            ticker = m.group(1)
            fp_intent = "Bypass-Matched"
        
    if ticker and not request.raw_data_mode:"""

if target in content:
    content = content.replace(target, replacement)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced app.py using strict target")
else:
    # Let's try splitting the content if the exact match fails
    print("Exact target not found! I will use regex substitution.")
    import re as pyre
    content = pyre.sub(
        r'# \[FAST-PATH\] Shorthand Directive Bypass.*?if ticker and not request.raw_data_mode:', 
        replacement, 
        content, 
        flags=pyre.DOTALL
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced app.py using regex dotall")
