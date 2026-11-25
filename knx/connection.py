#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  This file is part of SmartHomeNG.py.
#  https://www.smarthomeng.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

"""Connection helpers for the knxd (eibd) wire protocol"""

import socket
import struct
import time
from collections.abc import Callable, Sequence

from lib.network import Tcp_client

LENGTH_SIZE = 2


def frame_packet(data: bytes) -> bytearray:
    """Prefix a knxd request with its length as 2-byte big-endian integer"""
    framed = bytearray(len(data).to_bytes(LENGTH_SIZE, byteorder='big'))
    framed.extend(data)
    return framed


class KnxdFrameReader:
    """
    Reassembles knxd messages from the two-step reads of a ``Tcp_client``.

    knxd prefixes every message with its length. The client first reads
    ``LENGTH_SIZE`` bytes, which set ``client.terminator`` to the size of the message
    that follows, then reads that message. An instance tracks that state for exactly
    one connection.

    :param on_message: called with every complete message
    :param log_error: called with a description when a length prefix cannot be decoded
    """

    def __init__(self, on_message: Callable[[bytes], None], log_error: Callable[[str], None]) -> None:
        self._on_message = on_message
        self._log_error = log_error
        self._expect_length = True

    def reset(self) -> None:
        """Expect a length prefix next, e.g. after a new connection was established"""
        self._expect_length = True

    def feed(self, client: Tcp_client, data: bytes) -> None:
        """Process one chunk read from ``client``; usable as its ``data_received`` callback"""
        if self._expect_length:
            self._expect_length = False
            try:
                client.terminator = struct.unpack('>H', data)[0]
            except Exception:
                self._log_error(f'problem unpacking length: {data}')
            return
        self._expect_length = True
        client.terminator = LENGTH_SIZE
        self._on_message(data)


class CacheReadConnection:
    """
    Short-lived knxd connection which only carries cache reads.

    A connection on which knxd already opened the group communication (OPEN_GROUPCON)
    stops delivering group telegrams and rejects group packets after receiving a cache
    read, so cache reads outside the initial connect phase use a connection of their own.

    :param host: knxd host
    :param port: knxd port
    :param on_message: called with every message knxd sends back
    """

    CONNECT_TIMEOUT = 5.0

    def __init__(self, host: str, port: int, on_message: Callable[[bytes], None]) -> None:
        self._host = host
        self._port = port
        self._on_message = on_message

    def read(self, requests: Sequence[bytes], timeout: float, pause: float = 0.0) -> int:
        """
        Send the requests and wait for knxd to answer each of them, then close the connection.

        :param requests: unframed knxd requests, each answered by exactly one message
        :param timeout: seconds to wait for all answers after the last request was sent
        :param pause: seconds to wait between two requests
        :return: number of answers received
        :raises OSError: if the connection cannot be established or breaks
        """
        replies = 0
        if not requests:
            return replies
        with socket.create_connection((self._host, self._port), timeout=self.CONNECT_TIMEOUT) as sock:
            for request in requests:
                sock.sendall(frame_packet(request))
                time.sleep(pause)
            deadline = time.monotonic() + timeout
            while replies < len(requests):
                length = self._recv_exactly(sock, LENGTH_SIZE, deadline)
                if length is None:
                    break
                message = self._recv_exactly(sock, struct.unpack('>H', length)[0], deadline)
                if message is None:
                    break
                self._on_message(message)
                replies += 1
        return replies

    @staticmethod
    def _recv_exactly(sock: socket.socket, size: int, deadline: float) -> bytes | None:
        """Read exactly ``size`` bytes; None if the deadline passes or the peer closes first"""
        data = b''
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            sock.settimeout(remaining)
            try:
                chunk = sock.recv(size - len(data))
            except TimeoutError:
                return None
            if not chunk:
                return None
            data += chunk
        return data
