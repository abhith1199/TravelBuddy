import urllib.request
url = 'http://127.0.0.1:8000/browse-trips/'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = r.read().decode('utf-8', errors='replace')
    print('STATUS: OK')
    print(data[:4000])
except Exception as e:
    print('ERROR:', repr(e))
    import traceback
    traceback.print_exc()
