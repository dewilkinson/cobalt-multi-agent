def main():
    with open("backend/src/server/app.py", 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if "scanner_router" in line:
                print(f"{line_num}: {line.strip()}")

if __name__ == "__main__":
    main()
