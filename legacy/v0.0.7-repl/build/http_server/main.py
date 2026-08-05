import http.server

def run() -> None:
    server = http.server.HTTPServer(('', 8005), HelloHandler)
    server.serve_forever()
if __name__ == '__main__':
    run()


class HelloHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write('Hello, World!'.encode('utf-8'))
