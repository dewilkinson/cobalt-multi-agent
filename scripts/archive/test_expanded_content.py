import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')

divs = soup.find_all('div', class_=lambda c: c and 'expandCollapseIcon' in c)
for div in divs[:2]:
    parent_row = div.find_parent('div', class_=lambda c: c and 'gridRow' in c)
    if parent_row:
        print("--- ROW ---")
        print(parent_row.get_text(separator=' | ', strip=True))
