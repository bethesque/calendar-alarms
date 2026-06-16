from urllib.request import Request, urlopen
import urllib.request
import json

payload = {
    "id": 1,
    "jsonrpc": "2.0",
    "method": "Server.GetStatus",
}

request = urllib.request.Request(
    "http://192.168.20.3:1880/jsonrpc",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(request, timeout=5) as response:
    if response.status != 200:
        raise RuntimeError(f"HTTP {response.status}")

    data = json.load(response)
    print(json.dumps(data, indent=4))