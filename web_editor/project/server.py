"""Compiled from .human via .context — DO NOT EDIT."""

from http.server import HTTPServer, BaseHTTPRequestHandler

RESPONSE_BODY = b"Hello from the HTTP server"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond()

    def do_POST(self):
        self._respond()

    def do_PUT(self):
        self._respond()

    def do_DELETE(self):
        self._respond()

    def do_HEAD(self):
        self._respond()

    def do_OPTIONS(self):
        self._respond()

    def do_PATCH(self):
        self._respond()

    def _respond(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(RESPONSE_BODY)))
        self.end_headers()
        self.wfile.write(RESPONSE_BODY)

    def log_message(self, format, *args):
        pass


def run(host="localhost", port=8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, SimpleHandler)
    print(f"Serving on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
