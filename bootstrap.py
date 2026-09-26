"""Install the pinned PASSIVE mirror; never collect market data."""
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
    with open('sync.lock', 'a') as sync_lock:
        try:
            fcntl.flock(sync_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(0)
        for name, sha in {'mirror.py': '096b2a359d65cd433fd956c33e116eb7cec10f0ae40d9290f98d771f3d1e7302', 'cache_sync.py': 'd16b92a928ba3515160437413b019c87caa1da36485f23121d7ad7e33ac6b187', 'capture.php': '668cf09b2dfebd41c6a27539efa9add53bd8278aa009623b725c733ca3db6da3', 'sakura_runner.py': '2ef8c8d5c9d6f104376191fc263335f0d9b5bf5eac6d3c9f54a1461c2e9965f8'}.items():
            target = p / name
            if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                data = urllib.request.urlopen('https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/74205122129176f5d90ab6ff4bdae4bb9d94132e/' + name, timeout=20).read(200000)
                if hashlib.sha256(data).hexdigest() != sha:
                    raise ValueError('hash mismatch')
                temp = p / (name + '.tmp')
                temp.write_bytes(data)
                os.replace(temp, target)
    sys.path.insert(0, str(p))
    runpy.run_path(str(p / 'sakura_runner.py'), run_name='__main__')
except Exception as exc:
    status = pathlib.Path('/home/drexworld/www/fx-mirror-status.json')
    status.write_text(json.dumps({'ok': False, 'stage': 'bootstrap', 'error_type': type(exc).__name__, 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}))
    os.chmod(status, 0o644)
    sys.exit(1)
