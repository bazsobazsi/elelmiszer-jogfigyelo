#!/usr/bin/env python3
"""Send digest request to the elelmiszer-jogfigyelo server."""
import urllib.request
import json

url = "http://ai3.ballaizsolt.hu:8768/api/digest-and-send"
data = json.dumps({}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print(resp.status)
    print(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(e.code)
    print(e.read().decode("utf-8"))
except Exception as e:
    print(f"Error: {e}")