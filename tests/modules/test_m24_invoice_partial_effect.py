"""Real localhost HTTP receipts; no Stripe account or payment is used."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from app.modules.m24_billing.stripe_client import StripeClient


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['http', 'json'])
async def test_second_invoice_step_reports_accepted_item(failure):
    receipts = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            receipts.append((self.path, self.headers['Idempotency-Key']))
            if self.path.endswith('invoiceitems'):
                status, body = 200, b'{"id":"ii_fixture"}'
            elif failure == 'http':
                status, body = 500, b'{"error":"fixture"}'
            else:
                status, body = 200, b'invalid json'
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class LocalTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            url = request.url.copy_with(scheme='http', host='127.0.0.1', port=server.server_port)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=request.headers, content=await request.aread())
            return response

    try:
        with pytest.raises(RuntimeError, match='invoice item accepted; draft invoice outcome unknown'):
            await StripeClient('sk_test_fixture', LocalTransport()).create_invoice(
                'cus_fixture', 'fixture', 100, 'usd', 'approval-fixture'
            )
        assert receipts == [('/v1/invoiceitems', 'approval-fixture:invoice-item'),
                            ('/v1/invoices', 'approval-fixture:draft-invoice')]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
