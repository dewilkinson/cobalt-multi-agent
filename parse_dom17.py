import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')
for btn in soup.find_all(lambda tag: tag.name in ['a', 'button', 'span', 'div'] and 'export' in tag.get_text(strip=True).lower()):
    print('Found:', btn.name, btn.get('class'))
