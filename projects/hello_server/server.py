from http.server import BaseHTTPRequestHandler, HTTPServer


class Hello(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"hello world"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    HTTPServer(("", 8000), Hello).serve_forever()


if __name__ == "__main__":
    main()
