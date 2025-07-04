#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer

PORT = 8000
here = Path(__file__).parent / 'cache'


class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(here), **kwargs)

    def end_headers(self):
        self.send_my_headers()

        SimpleHTTPRequestHandler.end_headers(self)

    def send_my_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')


if __name__ == '__main__':
    if not here.is_dir():
        print('first, run: python make_backlog_data.py cache')
        exit(1)

    with TCPServer(('', PORT), Handler) as httpd:
        print(f'serving at port {PORT}')
        try:
            httpd.serve_forever()
        except (KeyboardInterrupt, SystemExit):
            print('shutting down...')
