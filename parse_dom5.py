import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')

def find_parent_row(element):
    parent = element.parent
    while parent:
        classes = parent.get('class', [])
        if isinstance(classes, list):
            c_str = ' '.join(classes).lower()
        else:
            c_str = str(classes).lower()
        if 'row' in c_str or parent.name == 'tr':
            return parent
        parent = parent.parent
    return None

elements = soup.find_all(string=lambda t: t and 'SNDK' in t)
for el in elements:
    row = find_parent_row(el)
    if row:
        print("Found row classes:", row.get('class'))
        print("Row text:", row.get_text(separator=' | ', strip=True))
        print("---")
