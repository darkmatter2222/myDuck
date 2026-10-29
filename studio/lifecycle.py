"""Identify only our server before replacing it. Never kill a port owner."""
import errno,json,os,signal,time
from pathlib import Path
from http.server import ThreadingHTTPServer

def identity(pid):
    try:
        args=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        if b'studio.server' not in args:return None
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None

def stop_existing(path):
    try:record=json.loads(path.read_text())
    except (OSError,ValueError):return False
    pid=record.get('pid');stamp=record.get('identity')
    if not isinstance(pid,int) or pid<=1 or not stamp or identity(pid)!=stamp:return False
    os.kill(pid,signal.SIGTERM)
    for _ in range(100):
        if identity(pid)!=stamp:return True
        time.sleep(.1)
    raise SystemExit('Existing Studio did not stop within 10 seconds. Check studio.log; no other process was terminated.')

def bind_server(port,handler):
    if not 1<=port<=65535:raise ValueError('Port must be between 1 and 65535')
    for candidate in range(port,min(port+20,65536)):
        try:return ThreadingHTTPServer(('127.0.0.1',candidate),handler)
        except OSError as exc:
            if exc.errno!=errno.EADDRINUSE:raise
    raise ValueError('No free port in the next 20 ports. Use ./start.sh --port NUMBER.')
