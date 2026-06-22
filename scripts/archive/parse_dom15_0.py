import bs4
import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = bs4.BeautifulSoup(text, 'html.parser')
for element in soup.find_all(string=re.compile(r'09:41\s*AM', re.IGNORECASE)):
    parent = element.parent
    print("Found time string:", repr(element.string))
    path = []
    p = parent
    while p and p.name != 'body':
        classes = p.get('class', [])
        c_str = ' '.join(classes) if isinstance(classes, list) else str(classes)
        path.append(f"{p.name}.{c_str}")
        p = p.parent
    print("Path:", " -> ".join(reversed(path)))
    break
