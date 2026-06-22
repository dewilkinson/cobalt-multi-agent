import bs4
import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = bs4.BeautifulSoup(text, 'html.parser')
elements = soup.find_all(string=re.compile(r'09:41 AM'))
for el in elements:
    parent = el.parent
    while parent and parent.name != 'body':
        print("Class:", parent.get('class'))
        parent = parent.parent
    break
