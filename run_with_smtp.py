#!/usr/bin/env python3
"""Wrapper to run serve.py with SMTP env vars."""
import os
import sys

# Set SMTP env vars
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"
os.environ["SMTP_USER"] = "debug"
os.environ["SMTP_PASS"] = "debug"
os.environ["EMAIL_FROM"] = "digest@elelmiszer-jogfigyelo.hu"
os.environ["EMAIL_TO"] = "digest@elelmiszer-jogfigyelo.hu"
os.environ["EMAIL_CC"] = ""
os.environ["EMAIL_ENABLED"] = "1"

# Import and run serve.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import serve
# serve.py has if __name__ == "__main__" block
# Let Flask run
serve.app.run(host="0.0.0.0", port=8768, debug=False)