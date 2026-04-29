import re
import bs4
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm|a\.m\.|p\.m\.)\b', text)
times += re.findall(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm|a\.m\.|p\.m\.)\b', text)

# Try parsing details out of DOM directly
soup = bs4.BeautifulSoup(text, 'html.parser')
print('Unique times found:', list(set(times)))

for row in soup.find_all('div', class_='gridRow'):
    t = row.get_text(separator=' | ', strip=True)
    if 'YOU BOUGHT' in t or 'YOU SOLD' in t:
        print("---")
        print("Row:", t)
