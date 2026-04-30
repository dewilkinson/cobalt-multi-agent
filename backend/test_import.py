try:
    print("SUCCESS")
except Exception:
    import traceback

    open("trace.txt", "w", encoding="utf-8").write(traceback.format_exc())
