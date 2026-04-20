import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import json

def fetch_ff_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NY_TZ = ZoneInfo("America/New_York")
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        high_impact_events = []
        for event in data:
            # We want High impact, maybe Medium. Let's filter for "High" impact.
            if event.get("impact") == "High":
                event_date_str = event.get("date", "")
                # example format: '2026-04-19T18:45:00-04:00'
                try:
                    dt = datetime.fromisoformat(event_date_str)
                    formatted_date = dt.astimezone(NY_TZ).strftime("%A, %I:%M %p EST")
                except:
                    formatted_date = event_date_str
                
                title = event.get("title", "Unknown Event")
                country = event.get("country", "")
                forecast = event.get("forecast", "")
                previous = event.get("previous", "")
                
                info = f"- **{country}**: {title} | {formatted_date} (Forecast: {forecast}, Prev: {previous})"
                high_impact_events.append(info)
        
        print("Scraped Events:")
        for ev in high_impact_events:
            print(ev)
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    fetch_ff_calendar()
