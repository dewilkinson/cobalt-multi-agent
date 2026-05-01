import os
from bs4 import BeautifulSoup
import re

debug_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "fidelity_extension_debug_dom.html"))
with open(debug_path, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and ('gridrow' in c.lower() or 'ao-row-container' in c.lower()))

for row in rows[:5]:
    text = row.get_text(separator=' ', strip=True)
    if 'UNH' in text or 'XLE' in text:
        print(repr(text))
