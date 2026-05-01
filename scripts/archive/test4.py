import urllib.request, json
try:
    req = urllib.request.urlopen('http://localhost:8000/api/brokerage/history?account_id=Rollover%20IRA&start_date=2026-04-30&end_date=2026-04-30')
    print('OK', req.read()[:50])
except urllib.error.HTTPError as e:
    print('ERROR', e.read())
