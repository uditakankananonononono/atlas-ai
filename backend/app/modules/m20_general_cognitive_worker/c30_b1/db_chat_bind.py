"""Read-only DB adapter for B1. No chat/tool/build-transcript table is queried."""
if __package__:
    from .chat_bind import ChatBinder, Refused, make_snapshot
else:
    from chat_bind import ChatBinder, Refused, make_snapshot

CHANNELS = ('WhatsApp', 'iMessage', 'SMS', 'RCS')

def ingest(connection, *, as_of):
    """SQLite connection; ts must be timezone-bearing ISO-8601 text.

    Take count and rows in one read transaction owned by the caller. The adapter
    never commits or writes. For SQLite use mode=ro and an explicit BEGIN.
    The julianday comparison normalizes offsets; this adapter is SQLite-only.
    """
    where = "author = ? AND service IN (?, ?, ?, ?) AND julianday(ts) <= julianday(?)"
    parameters = ('user', *CHANNELS, as_of)
    owner_total = connection.execute(
        'SELECT COUNT(*) FROM phone_messages WHERE author = ? AND service IN (?, ?, ?, ?)',
        ('user', *CHANNELS)).fetchone()[0]
    total = connection.execute('SELECT COUNT(*) FROM phone_messages WHERE ' + where, parameters).fetchone()[0]
    if owner_total != total:
        raise Refused('PLAN_REFUSED_DB_COUNT')
    values = connection.execute(
        'SELECT message_id, body, ts, author, service, conversation_id FROM phone_messages WHERE ' + where +
        ' ORDER BY ts, message_id', parameters).fetchall()
    columns = ('message_id', 'body', 'ts', 'author', 'service', 'conversation_id')
    rows = [dict(zip(columns, row)) for row in values]
    return make_snapshot(rows, as_of=as_of, observed_total=total)

def reconcile(connection, binder):
    fresh = ingest(connection, as_of=binder.snapshot['as_of'])
    return binder.reconcile(fresh['rows'])
