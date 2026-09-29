"""Smoke-test the actual archive after moving it to a clean, spaced path."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def get(base, route):
    with urllib.request.urlopen(base + route, timeout=2) as response:
        return response.read()


def wait_ready(child, base, route):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise AssertionError('Portable process exited before it became ready.')
        try:
            return json.loads(get(base, route))
        except OSError:
            time.sleep(.2)
    raise AssertionError('Portable process did not become ready.')


def main():
    archive = ROOT / 'dist/Droid-Studio-Windows-x64.zip'
    with tempfile.TemporaryDirectory(prefix='Droid portable test ') as temporary:
        folder = Path(temporary)
        with ZipFile(archive) as zipped:
            assert zipped.testzip() is None
            for name in zipped.namelist():
                assert not {'__pycache__', '.venv', 'pip', 'tests', 'outputs', 'data', 'cache'}.intersection(Path(name).parts), name
                assert not name.endswith(('.log', '.pyc', '.map')), name
            zipped.extractall(folder)
        app = folder / 'Droid Studio'
        python = app / 'runtime/python.exe'
        env = dict(os.environ, PATH=os.path.join(os.environ['SystemRoot'], 'System32'),
                   PYTHONHOME=str(folder / 'not-a-python'), PYTHONPATH=str(folder / 'not-a-library'))
        options = dict(cwd=app, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        code = '''import json,sys,subprocess
import ssl,sqlite3,ctypes,asyncio
import uiautomator2,uiautodev.app,fastapi,PIL,lxml.etree,pydantic_core
from adbutils._utils import adb_path
from pathlib import Path
root=Path.cwd()
assert all(Path(p).is_relative_to(root) for p in sys.path), sys.path
adb=adb_path()
assert Path(adb).is_relative_to(root), adb
subprocess.run([adb,'version'],check=True,stdout=subprocess.PIPE)
print(json.dumps({'isolated':sys.flags.isolated,'runtime':sys.executable,'bundled_adb':True}))
'''
        result = subprocess.run([python, '-B', '-c', code], **options, capture_output=True, text=True, timeout=25)
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip())
        children = []
        try:
            with (folder / 'smoke.log').open('wb') as log:
                port = free_port()
                child = subprocess.Popen([python, '-B', 'app.py', '--no-browser', '--port', str(port)], **options, stdout=log, stderr=log)
                children.append(child)
                base = f'http://127.0.0.1:{port}'
                session = wait_ready(child, base, '/api/session')
                assert session['app'] == 'droid-studio' and session['device']['demo']
                for route in ['/', '/app.js', '/style.css', '/vendor/blockly_compressed.js', '/vendor/msg/de.js', '/vendor/media/sprites.svg', '/examples/variablen.json', '/api/screen']:
                    assert len(get(base, route)) > 10, route
                request = urllib.request.Request(base + '/api/run', data=json.dumps({'program': [{'op': 'wait', 'seconds': 0}]}).encode(), headers={'Content-Type':'application/json','X-Studio-Token': session['token']})
                with urllib.request.urlopen(request, timeout=3) as response:
                    assert response.status == 200
                for _ in range(30):
                    state = json.loads(get(base, '/api/state'))
                    if state['run']['status'] == 'completed':
                        break
                    time.sleep(.1)
                assert state['run']['status'] == 'completed', state['run']
                print('Portable Studio: assets, demo screen and execution OK')
                inspector_port = free_port()
                inspector = subprocess.Popen([python, '-B', '-m', 'uiautodev', 'server', '--host', '127.0.0.1', '--port', str(inspector_port), '--no-browser', '--offline', '--server-url', 'https://uiauto2.devsleep.com'], **options, stdout=log, stderr=log)
                children.append(inspector)
                info = wait_ready(inspector, f'http://127.0.0.1:{inspector_port}', '/api/info')
                assert info['description'] == 'client for https://web.uiauto.dev'
                print('Portable uiautodev: startup and API OK')
        finally:
            for child in reversed(children):
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        print('ZIP verification passed; no development runtime required.')


if __name__ == '__main__':
    main()
