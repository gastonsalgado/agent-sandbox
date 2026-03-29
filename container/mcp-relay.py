#!/usr/bin/env python3
"""Minimal stdio-to-unix-socket bridge for MCP traffic."""

import argparse
import os
import select
import socket
import sys

BUFFER_SIZE = 65536


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/var/run/mcp.sock")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(args.socket)

    stdin_fd = sys.stdin.buffer.fileno()
    sock_fd = sock.fileno()

    try:
        while True:
            readable, _, _ = select.select([stdin_fd, sock_fd], [], [])
            for fd in readable:
                if fd == stdin_fd:
                    data = os.read(stdin_fd, BUFFER_SIZE)
                    if not data:
                        return
                    sock.sendall(data)
                elif fd == sock_fd:
                    data = sock.recv(BUFFER_SIZE)
                    if not data:
                        return
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
    finally:
        sock.close()


if __name__ == "__main__":
    main()
