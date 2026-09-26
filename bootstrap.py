"""Install the pinned ZARJPY mirror outside the public web root."""
import os, sys, pathlib, hashlib, urllib.request, json, datetime, runpy, fcntl
os.umask(0o077)
p = pathlib.Path('/home/drexworld/fx-mirror')
p.mkdir(mode=0o700, exist_ok=True)
os.chmod(p, 0o700)
os.chdir(p)
lock = open('bootstrap.lock', 'a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
try:
    for name, sha in [('mirror.py', '096b2a359d65cd433fd956c33e116eb7cec10f0ae40d9290f98d771f3d1e7302'), ('sakura_runner.py', '9d0dd1637de5319d9ec9c5d85fab26c63fa3e8d6a0156e402adbaf76929b9b39')]:
        f = p / name
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != sha:
            data = urllib.request.urlopen('https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/8ea291d99fc452911da1029a2d9c2c9296b0ba47/' + name, timeout=20).read(200000)
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError('hash mismatch')
            temp = p / (name + '.tmp')
            temp.write_bytes(data)
            os.replace(temp, f)
    sys.path.insert(0, str(p))
    runpy.run_path(str(p / 'sakura_runner.py'), run_name='__main__')
except Exception as exc:
    status = pathlib.Path('/home/drexworld/www/fx-mirror-status.json')
    status.write_text(json.dumps({'ok': False, 'stage': 'bootstrap', 'error_type': type(exc).__name__, 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}))
    os.chmod(status, 0o644)
    sys.exit(1)
