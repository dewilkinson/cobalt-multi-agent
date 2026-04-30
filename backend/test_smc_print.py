import os
import sys

old_stdout = sys.stdout
sys.stdout = open(os.devnull, "w")
from smartmoneyconcepts import smc

sys.stdout.close()
sys.stdout = old_stdout

import pandas as pd

df = pd.DataFrame({"Open": [1] * 200, "High": [2] * 200, "Low": [1] * 200, "Close": [1.5] * 200, "Volume": [100] * 200})
print("Calling swing_highs_lows")
smc.swing_highs_lows(df)
print("Done")
