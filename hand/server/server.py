from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Hello, World!')

server = HTTPServer(('localhost', 8000), Handler)
print('Serving on http://localhost:8000')
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.server_close()
