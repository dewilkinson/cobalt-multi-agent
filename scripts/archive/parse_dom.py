import bs4

with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')

print("Looking for tables/grids...")
for row in soup.find_all(['tr', 'div']):
    classes = row.get('class', [])
    if isinstance(classes, list):
        c_str = ' '.join(classes).lower()
    else:
        c_str = str(classes).lower()
        
    if 'row' in c_str or 'grid' in c_str or 'activity' in c_str:
        text = row.get_text(strip=True, separator=' | ')
        if 'Buy' in text or 'Sell' in text or 'Bought' in text or 'Sold' in text or 'Executed' in text or 'Filled' in text:
            if len(text) < 500:
                print("Found row:", text)
