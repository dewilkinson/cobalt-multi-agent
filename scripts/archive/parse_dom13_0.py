import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')
links = soup.find_all(lambda tag: tag.name in ['a', 'button', 'div', 'span'] and 'download' in tag.get_text(strip=True).lower())
for link in links:
    print('Found Element:', link.name, link.get('class'), link.get('title'))
