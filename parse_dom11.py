with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
idx = text.find('09:41 AM')
print(text[max(0, idx-100):idx+100])
