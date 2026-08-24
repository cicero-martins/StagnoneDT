"""Serve the WetWise portal with caching disabled.

python -m http.server lets the browser cache index.html and the data payload,
which during iteration means edits appear not to have landed at all.  This
serves the same directory but tells the browser never to store anything.

    python scripts/serve_wetwise.py [port]
"""
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'outputs' / 'wetwise_tab' / 'demo_hydrodynamics'


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def send_response(self, *args, **kwargs):       # quieter log
        super().send_response(*args, **kwargs)

    def log_message(self, fmt, *args):
        if '304' not in (args[1] if len(args) > 1 else ''):
            sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    handler = partial(NoCacheHandler, directory=str(DIRECTORY))
    print(f'serving {DIRECTORY}\n  http://localhost:{port}  (no-store)')
    HTTPServer(('127.0.0.1', port), handler).serve_forever()


if __name__ == '__main__':
    main()
