"""Compiled directly from .human — DO NOT EDIT."""
import http.server
import socketserver
import threading
import urllib.request
import time

PORT = 8080

class SimpleHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello from the test HTTP server!"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[SERVER] {self.address_string()} - {format % args}")


def run_server(httpd):
    httpd.serve_forever()


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), SimpleHandler) as httpd:
        httpd.allow_reuse_address = True
        thread = threading.Thread(target=run_server, args=(httpd,), daemon=True)
        thread.start()
        print(f"[TEST] Server started on port {PORT}")
        time.sleep(0.5)

        # Test GET request
        url = f"http://localhost:{PORT}/"
        print(f"[TEST] Sending GET request to {url}")
        with urllib.request.urlopen(url) as response:
            status = response.status
            body = response.read().decode()
        print(f"[TEST] Status: {status}")
        print(f"[TEST] Body: {body}")

        assert status == 200, f"Expected 200, got {status}"
        assert body == "Hello from the test HTTP server!", f"Unexpected body: {body}"
        print("[TEST] All assertions passed.")

        httpd.shutdown()
        print("[TEST] Server stopped.")
