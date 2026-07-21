import http.server
import json
from functools import partial

PORT = 8000

routes = {}

def register_route(method, path, handler):
    routes[(method.upper(), path)] = handler

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def _handle_request(self, method):
        key = (method, self.path)
        if key in routes:
            routes[key](self)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def log_message(self, format, *args):
        pass

def hello_world_handler(request):
    body = b"Hello, World!"
    request.send_response(200)
    request.send_header("Content-Type", "text/plain")
    request.send_header("Content-Length", str(len(body)))
    request.end_headers()
    request.wfile.write(body)

register_route("GET", "/", hello_world_handler)
register_route("POST", "/", hello_world_handler)

def run(port=PORT):
    server = http.server.HTTPServer(("", port), RequestHandler)
    server.serve_forever()

if __name__ == "__main__":
    run(PORT)