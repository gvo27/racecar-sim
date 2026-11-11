#!/usr/bin/env python3
"""LSP smoke test (stdlib only).

Usage: smoke.py <command> [args...]
Starts the command, sends an LSP `initialize` request (Content-Length framing) and
expects a response with `result.capabilities` within 30 s. Exit 0 = valid response.
"""
import json
import os
import subprocess
import sys
import threading

TIMEOUT_S = 30


def frame(payload):
    body = json.dumps(payload).encode()
    return b'Content-Length: %d\r\n\r\n' % len(body) + body


def read_message(stream):
    """Read one framed message. Return the decoded object, or None at end of stream."""
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        name, _, value = line.partition(b':')
        if name.lower() == b'content-length':
            length = int(value)
    if length is None:
        return None
    return json.loads(stream.read(length))


def main(argv):
    if not argv:
        print('usage: smoke.py <command> [args...]', file=sys.stderr)
        return 2
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    result = {}

    def reader():
        # skip notifications and server requests until the response with id 1
        while True:
            msg = read_message(proc.stdout)
            if msg is None:
                return
            if msg.get('id') == 1 and ('result' in msg or 'error' in msg):
                result['msg'] = msg
                return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'processId': os.getpid(), 'rootUri': None, 'capabilities': {}}}
    try:
        proc.stdin.write(frame(request))
        proc.stdin.flush()
    except BrokenPipeError:
        print('FAIL: command closed stdin: %s' % ' '.join(argv), file=sys.stderr)
        return 1
    thread.join(TIMEOUT_S)
    ok = False
    msg = result.get('msg')
    if msg is None:
        print('FAIL: no initialize response within %d s: %s' % (TIMEOUT_S, ' '.join(argv)),
              file=sys.stderr)
    elif 'result' in msg and 'capabilities' in msg['result']:
        ok = True
        name = msg['result'].get('serverInfo', {}).get('name', 'server')
        print('PASS: initialize answered by %s' % name)
    else:
        print('FAIL: invalid initialize response: %s' % json.dumps(msg)[:200], file=sys.stderr)
    try:
        proc.stdin.write(frame({'jsonrpc': '2.0', 'id': 2, 'method': 'shutdown'}))
        proc.stdin.write(frame({'jsonrpc': '2.0', 'method': 'exit'}))
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
