import socket
import threading
import os
import sys
DEFAULT_PORT = 8080
WORKING_DIR = os.getcwd()
MIME_TYPES = {'.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript'}
def get_mime_type(path):
    _, ext = os.path.splitext(path)
    return MIME_TYPES.get(ext, 'text/plain')
def build_response(status_code, reason, body, content_type='text/plain'):
    status_line = f'HTTP/1.1 {status_code} {reason}\r\n'
    headers = f'Content-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n'
    return (status_line + headers + '\r\n').encode() + body
def handle_connection(conn, addr):
    method = path = ''
    status_code = 500
    try:
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        header_section, _, body_data = data.partition(b'\r\n\r\n')
        lines = header_section.decode(errors='replace').split('\r\n')
        request_line = lines[0]
        parts = request_line.split(' ')
        method = parts[0] if len(parts) > 0 else ''
        path = parts[1] if len(parts) > 1 else '/'
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                k, _, v = line.partition(':')
                headers[k.strip().lower()] = v.strip()
        content_length = int(headers.get('content-length', 0))
        while len(body_data) < content_length:
            chunk = conn.recv(4096)
            if not chunk:
                break
            body_data += chunk
        if method not in ('GET', 'POST'):
            response = build_response(405, 'Method Not Allowed', b'Method Not Allowed')
            status_code = 405
        else:
            file_path = os.path.normpath(os.path.join(WORKING_DIR, path.lstrip('/')))
            if not file_path.startswith(WORKING_DIR):
                response = build_response(404, 'Not Found', b'Not Found')
                status_code = 404
            elif os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                mime = get_mime_type(file_path)
                response = build_response(200, 'OK', file_bytes, mime)
                status_code = 200
            else:
                response = build_response(404, 'Not Found', b'Not Found')
                status_code = 404
        conn.sendall(response)
    except Exception:
        try:
            conn.sendall(build_response(500, 'Internal Server Error', b'Internal Server Error'))
        except Exception:
            pass
    finally:
        conn.close()
        print(f'{method} {path} {status_code}', flush=True)
def run(port=DEFAULT_PORT):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', port))
    server.listen()
    print(f'Serving on port {port}', flush=True)
    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_connection, args=(conn, addr), daemon=True)
        t.start()
if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run(port)
