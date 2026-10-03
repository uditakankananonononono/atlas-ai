@pytest_asyncio.fixture
async def setup_mode(tmp_path):
    class Site(BaseHTTPRequestHandler):
        posts = []
        keys = []
        commands = []
        extra_field = None
        submit_attr = None
        html_hook = None
        post_paths = []
        redirect = None
        redirects = {}
        hits = []
        def log_message(self, *args): pass
        def do_GET(self):
            self.hits.append((self.headers['Host'], 'GET', self.path, ''))
            if self.path == '/throttle':
                self.send_response(429); self.end_headers(); return
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            if self.path == '/captcha':
                html = 'captcha'
            else:
                html = '''<html><body><div id="account"></div><script>
                document.querySelector('#account').textContent=localStorage.getItem('owner')||'';
                </script><a class="source" href="/idea">Offer a small tutoring pilot and measure actual interest.</a>
                <form method="post" action="/publish"><p id="terms">Free publication. No fees.</p>
                <label>Public draft<textarea id="draft" name="draft"></textarea></label>
                <input name="audience" value="public"><input id="run_id" name="run_id"><button id="publish">Publish once</button></form>'''
                if self.submit_attr and self.path == '/compose':
                    html = html.replace('<button id="publish"', '<button id="publish" '+self.submit_attr[0]+'="'+self.submit_attr[1]+'"')
                if self.extra_field and self.path == '/compose':
                    html = html.replace('</form>', '<input name="'+self.extra_field+'" value="DO_NOT_COPY"></form>')
                if Site.html_hook and self.path == '/compose':
                    html = Site.html_hook(html)
                if self.path == '/receipt' and self.posts:
                    html += '<div id="receipt">'+str(len(self.posts))+'</div><div id="published">'+self.posts[-1]+'</div><div id="receipt_account">owner</div><div id="receipt_run">'+self.keys[-1]+'</div>'
                html += '</body></html>'
            self.wfile.write(html.encode())
        def do_POST(self):
            from urllib.parse import parse_qs
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            self.post_paths.append(self.path)
            self.hits.append((self.headers['Host'], self.command, self.path, body))
            if self.path in Site.redirects:
                self.send_response(Site.redirects[self.path][0]); self.send_header('Location', Site.redirects[self.path][1]); self.end_headers(); return
            if self.path == '/publish' and Site.redirect:
                self.send_response(Site.redirect[0]); self.send_header('Location', Site.redirect[1]); self.end_headers(); return
            if self.path != '/publish':
                self.send_response(200); self.end_headers(); return
            self.posts.append(parse_qs(body)['draft'][0])
            self.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303); self.send_header('Location', '/receipt'); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    engine = create_engine(f'sqlite:///{tmp_path}/sql.db'); Base.metadata.create_all(engine)
    sql = sessionmaker(bind=engine, expire_on_commit=False)
    approvals, registry = Service(sql), BridgeRegistry(sql)
    identity = DeviceIdentity.load_or_create(tmp_path/'device.pem')
    challenge = registry.create_challenge('tenant')
    caps = ['navigate', 'extract', 'screenshot', 'read_values', 'fill', 'click_submit']
    paired = registry.confirm_pairing(challenge['server_nonce'], challenge['code'], name='Local owner', public_key=identity.public_key_pem(), capabilities=caps)
    config = DaemonConfig(device_id=paired['device_id'], command_secret=paired['command_secret'], capabilities=caps, pacing_seconds=0, browser_args=ARGS(tmp_path), consumed_path=str(tmp_path/'consumed.json'))
    daemon = Daemon(config, identity); Site.daemon = daemon
    pw, browser = await start_mode(daemon, config, tmp_path)
    page = await daemon.browser.page('experiment')
    await page.goto(origin)
    # Owner login handoff, not an Atlas fill of any credential.
    await page.evaluate("localStorage.setItem('owner','owner')")
    await page.reload()
    class Wire:
        async def send_json(self, command):
            Site.commands.append(command)
            answer = await daemon.execute(command)
            await connection.handle_message(answer)
    connection = DaemonConnection(Wire(), paired['device_id'], 2)
    # Local fake-site tests do not need human-site pacing. Production clamps >=2s.
    connection.pacing_seconds = 0
    hub = ConnectionHub(); await hub.register(connection)
    sessions = BridgedSessions(registry, hub)
    recipe = BrowserRecipe('local_fixture', origin, origin+'/discover', origin+'/compose', '#account', '.source', '#draft', '#publish', '#terms', 'Free publication. No fees.', '#receipt', '#published', '#receipt_account', '#run_id', '#receipt_run', ('draft', 'audience', 'run_id'), True)
    store = LoginRunStore(tmp_path/'runs.db')
    def runner(recipes=None):
        return build_login_runner(store=store, sessions=sessions, approvals=approvals,
            recipes=recipes or {'local_fixture': recipe}, receipt_key=b'k'*32)
    yield runner, recipe, approvals, registry, paired, page, Site, tmp_path
    await stop_mode(daemon, pw, browser); server.shutdown(); thread.join(); server.server_close()


