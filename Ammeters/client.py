from socket import socket, AF_INET, SOCK_STREAM
from typing import Optional


SOCKET_TIMEOUT_SECONDS = 5

def request_current_from_ammeter(port: int, command: bytes) -> Optional[float]:
    with socket(AF_INET, SOCK_STREAM) as s:
        s.settimeout(SOCKET_TIMEOUT_SECONDS)
        s.connect(('localhost', port))
        s.sendall(command)
        data = s.recv(1024)
        if data:
            value = float(data.decode('utf-8'))
            print(f"Received current measurement from port {port}: {value:.3f} A")
            return value
        return None

