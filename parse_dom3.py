import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')
print(soup.get_text(separator=' | ', strip=True)[:3000])
