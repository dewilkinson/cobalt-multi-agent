import os, sys, time, tempfile
print("Parent")
wrapper_path = os.path.join(tempfile.gettempdir(), "vli_restarter.py")
with open(wrapper_path, "w") as f:
    f.write(f"""import time, os, sys
print("Wrapper running")
time.sleep(2.0)
try:
    os.remove({repr(wrapper_path)})
except: pass
print("Wrapper executing final child")
os.execv(sys.executable, {repr([sys.executable, "-c", "print('Final Child')"])})
""")
os.execv(sys.executable, [sys.executable, wrapper_path])
