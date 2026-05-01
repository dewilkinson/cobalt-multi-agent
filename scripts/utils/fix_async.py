import sys

file_path = 'backend/src/tools/finance.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        loop = asyncio.get_event_loop()
        tasks = [fetch_av_concurrently(t) for t in mapped_tickers]
        
        try:
            results = asyncio.run(asyncio.gather(*tasks))
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            results = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))'''

replacement = '''        tasks = [fetch_av_concurrently(t) for t in mapped_tickers]
        
        async def run_tasks():
            return await asyncio.gather(*tasks)
            
        try:
            results = asyncio.run(run_tasks())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            results = asyncio.get_event_loop().run_until_complete(run_tasks())'''

if target in text:
    text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('fixed')
else:
    print('not found')
