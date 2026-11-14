"""Loopback-only development server. Uses an in-memory store; no AWS calls."""
import json, secrets, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from service import App, MemoryStore, password_hash

salt=secrets.token_hex(16)
app=App(MemoryStore(),{'gateway':secrets.token_urlsafe(32),'salt':salt,'admin_hash':password_hash('admin',salt),'access_hash':password_hash('AWS',salt),'stream_role':''})
lock=threading.RLock()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):self.process()
    def do_POST(self):self.process()
    def do_PUT(self):self.process()
    def do_PATCH(self):self.process()
    def do_DELETE(self):self.process()
    def log_message(self,format,*args):pass
    def process(self):
        from urllib.parse import urlsplit
        headers={k.lower():v for k,v in self.headers.items()}
        headers.update({'x-aegis-gateway':app.config['gateway'],'x-aegis-viewer':'loopback-development'})
        size=int(self.headers.get('Content-Length',0))
        if size>350000:self.send_error(413);return
        event={'rawPath':urlsplit(self.path).path,'headers':headers,'requestContext':{'http':{'method':self.command}},'body':self.rfile.read(size).decode() if size else None}
        with lock:r=app.handle(event)
        import base64
        body=base64.b64decode(r['body']) if r.get('isBase64Encoded') else r['body'].encode()
        self.send_response(r['statusCode'])
        for k,v in r.get('headers',{}).items():self.send_header(k,v)
        for cookie in r.get('cookies',[]):self.send_header('Set-Cookie',cookie.replace('; Secure',''))
        self.send_header('Content-Length',len(body));self.end_headers();self.wfile.write(body)

if __name__=='__main__':
    print('Aegis local service: http://127.0.0.1:8770',flush=True)
    print('In-memory development data. AWS liveness is disabled locally.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8770),Handler).serve_forever()
