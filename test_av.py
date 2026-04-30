import os, requests
from dotenv import load_dotenv
load_dotenv('backend/.env')
url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=EDSA&apikey={os.environ.get('ALPHA_VANTAGE_API_KEY')}&limit=2"
print(requests.get(url).json())
