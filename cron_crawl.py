#!/usr/bin/env python3
"""Cron crawl trigger - POST to local or remote crawler endpoint"""
import urllib.request, urllib.error, json, sys, os

url = "http://ai3.ballaizsolt.hu:8768/api/crawl"
data = json.dumps({}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    resp = urllib.request.urlopen(req, timeout=120)
    result = resp.read().decode('utf-8')
    print(f"Status: {resp.status}")
    print(result)
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"Status: {e.code}")
    print(body)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)