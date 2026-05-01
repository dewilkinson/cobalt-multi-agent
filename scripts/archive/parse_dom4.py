import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f, 'html.parser')
text = soup.get_text()
print('CC in text:', 'CC' in text)
print('SNDK in text:', 'SNDK' in text)
print('BOUGHT in text:', 'BOUGHT' in text)
print('SOLD in text:', 'SOLD' in text)
print('Buy in text:', 'Buy' in text)
print('Sell in text:', 'Sell' in text)
