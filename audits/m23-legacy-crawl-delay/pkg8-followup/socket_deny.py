"""Additional offline guard: forbid direct socket connects in probe subprocesses."""
import socket

def pytest_configure(config):
    def deny(*args, **kwargs):
        raise AssertionError('pkg8 offline probe: socket connect forbidden')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
