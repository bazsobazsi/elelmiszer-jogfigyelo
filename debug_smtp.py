#!/usr/bin/env python3
"""
Debug SMTP server — captures emails and logs them.
Does NOT deliver, just prints to stdout.
"""
import asyncore
from smtpd import SMTPServer
import logging

class DebugSMTPServer(SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        log = logging.getLogger('debug_smtp')
        log.info(f"FROM: {mailfrom}")
        log.info(f"TO: {rcpttos}")
        log.info(f"---EMAIL START---")
        log.info(data.decode('utf-8', errors='replace'))
        log.info(f"---EMAIL END---")
        return

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1025
    server = DebugSMTPServer(('0.0.0.0', port), None)
    print(f"Debug SMTP server on port {port}...")
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        print("Shutting down.")