import asyncio, threading, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0,'.')
from playwright.async_api import async_playwright
from app.modules.m13_browser_agent.session_bridge.form_guard import parse_set_cookie
CASES = ['a=1; Max-Age=1_000','a=1; Max-Age=١٢٣','a=1; Max-Age=+5','a=1; Max-Age=5.5','a=1; Max-Age= 50','a=1; Max-Age=-1','a=1; Max-Age=0',
 'a=1; Expires=Thu, 01 Jan 1970 00:00:01 GMT','a=1; Expires=Wed, 21 Oct 2037 07:28:00 GMT','a=1; Expires=Wed, 21 Oct 99 07:28:00 GMT','a=1; Expires=garbage',
 'a=1; Max-Age=abc; Expires=Wed, 21 Oct 2037 07:28:00 GMT','a b=1','=v','v','a=b=c','a=1;;;Path=/x','a=1; Path=relative','a=1; Path=/x/','a=1; Domain=127.0.0.1',
 'a=1; Domain=.127.0.0.1','a=1; Domain=localhost','a=1; SameSite=none','a=1; SameSite=None; Secure','a=1; SameSite=lax','a=1; samesite=STRICT','a=1; Secure',
 '__Host-a=1; Secure; Path=/','__Secure-a=1','a=" quoted "','a=1; HttpOnly','a="1;2"','  a  =  1  ','a=1; Max-Age=99999999999','a=1; Max-Age=-99999999999999999999',
 'a=1; Max-Age=0; Max-Age=500','a=1; Max-Age=500; Max-Age=0','a=1; Path=/; Path=/y','a=\x7f', 'a=1; Partitioned; Secure','a=%20x','a=1; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=500',
 'a=1; Max-Age=400000000','a=1; Max-Age=34560000','a=1; Max-Age=34560001', 'a=é']
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        i=int(self.path.strip('/')) if self.path.strip('/').isdigit() else None
        self.send_response(200); self.send_header('Content-Type','text/html')
        if i is not None:
            self.send_header('Set-Cookie', CASES[i].encode('utf-8','surrogateescape').decode('latin-1'))
        self.end_headers(); self.wfile.write(b'ok')
srv=ThreadingHTTPServer(('127.0.0.1',0),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{srv.server_port}'
def norm(c):
    if not c: return None
    return (c['name'],c['value'],c.get('path'),c.get('secure'),c.get('httpOnly'),c.get('sameSite'), 'sess' if c['expires']==-1 else ('exp' if c['expires']>time.time()+0 else 'past'), None if c['expires']==-1 else round((c['expires']-time.time())/86400))
async def main():
    async with async_playwright() as pw:
        b=await pw.chromium.launch()
        for i,raw in enumerate(CASES):
            real=await b.new_context(); p=await real.new_page(); await p.goto(f'{base}/{i}')
            rc=[norm(c) for c in await real.cookies()]; await real.close()
            mine=await b.new_context(); 
            try:
                parsed=parse_set_cookie(f'{base}/{i}',raw)
            except Exception as e: parsed=f'EXC {e!r}'
            mc=[]
            if isinstance(parsed,dict) and 'set' in parsed:
                try: await mine.add_cookies([parsed['set']]); mc=[norm(c) for c in await mine.cookies()]
                except Exception as e: mc=f'ADDERR {str(e)[:60]}'
            elif parsed is None: mc='REJECTED'
            elif isinstance(parsed,dict): mc='DELETE'
            else: mc=parsed
            await mine.close()
            flag = '' if rc==mc or (rc==[] and mc in ('REJECTED','DELETE')) else '   <<<< DIFF'
            print(repr(raw)[:60], '\n   chromium:', rc, '\n   parser  :', mc, flag)
        await b.close()
if __name__ == "__main__":
    asyncio.run(main())
