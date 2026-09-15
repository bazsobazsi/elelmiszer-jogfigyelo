#!/bin/sh
python3 -c "
import os, urllib.request
port = os.environ.get('PORT', '8768')
urllib.request.urlopen(f'http://localhost:{port}/api/health').read()
" || exit 1