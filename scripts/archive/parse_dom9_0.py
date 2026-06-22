import bs4
import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = bs4.BeautifulSoup(text, 'html.parser')
for row in soup.find_all('div', class_='gridRow'):
    t = row.get_text(separator=' | ', strip=True)
    if 'YOU BOUGHT' in t or 'YOU SOLD' in t:
        print("Row Summary:", t)
        # Look for details container inside the row
        details = row.find(class_=lambda x: x and 'details' in x.lower())
        if details:
            print("  Details:", details.get_text(separator=' | ', strip=True))
        else:
            # Maybe the details are in a sibling or inside a specific child
            child_text = row.get_text(separator=' | ', strip=True)
            times = re.findall(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm)\b', child_text)
            if times:
                print("  Times found in row:", times)
        print("---")
