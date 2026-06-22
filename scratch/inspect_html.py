def main():
    filepath = "backend/public/vli_dashboard.html"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Total characters: {len(content)}")
    
    # Search for api endpoints
    import re
    matches = re.findall(r'[\'"]/api/vli/[a-zA-Z0-9_\-/]+[\'"]', content)
    print("\nAPI endpoints found in HTML:")
    for m in set(matches):
        print(f"  {m}")
        
    # Search for keywords
    for keyword in ["fetch", "candidate", "strike", "combat"]:
        count = content.lower().count(keyword)
        print(f"Keyword '{keyword}' count: {count}")

if __name__ == "__main__":
    main()
