# Sirve el juego (carpeta JUEGO) y guarda los cuadros que el navegador le envia:
# POST /save?name=escena/0001.jpg  (cuerpo: data URL)  ->  BEHANCE/cuadros-juego/escena/0001.jpg
import base64, http.server, os, sys, urllib.parse
ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(ROOT, '..'))
FRAMES = os.path.abspath(os.path.join(ROOT, '..', '..', os.environ.get('BEHANCE_DIR', 'BEHANCE'), 'cuadros-juego'))
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WEB, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_POST(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = q['name'][0].replace('..', '')
        data = self.rfile.read(int(self.headers['Content-Length'])).decode()
        path = os.path.join(FRAMES, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data.split(',', 1)[1]))
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
