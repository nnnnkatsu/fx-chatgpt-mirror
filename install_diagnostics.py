RELEASE='6bf555fcf4f5fdec84069265bf6b913aa4b51b8b'
MANIFEST={'mirror.py': '71e97b5dff750d19efbfdf274ec9632346131d43910cb7fbc71b67594a8f90c9', 'cache_sync.py': 'ac7be1983dac905ef0988777beeb08d8c8181514d5c62fd235c163b5767ae84d', 'observed_sync.py': '3093964aa32670af35ecf48a841d6c36498495e9220c9e52184729e6150a00cc', 'sakura_runner.py': 'e2e83f1f8a54331b68f337a23763350d3f28dfe350d5f4fda33b56168f026cfc'}
PREVIOUS={'mirror.py': '84186ab0e36545f4a030dcfbb6d6225d05f25d212b3f07558a3f6989dda2f3ce', 'cache_sync.py': '8e969f0ba0b1cf3a3fc794192b670605baf757dd86739a734503cddbff8b07b5', 'sakura_runner.py': 'a102e09180ed3dbc185803650064c186e9166d579fbfbf50db71c5bf7dbed744'}
import os,sys,json,hashlib,pathlib,urllib.request,fcntl,runpy
from datetime import datetime,timezone
ROOT=pathlib.Path('/home/drexworld/fx-mirror')
STATUS=pathlib.Path('/home/drexworld/www/fx-mirror-install.json')
def sha(data): return hashlib.sha256(data).hexdigest()
def report(value):
    value.update(checked_at_utc=datetime.now(timezone.utc).isoformat(),upstream_requests=0)
    temp=STATUS.with_suffix('.tmp'); temp.write_text(json.dumps(value)); os.chmod(temp,0o644); os.replace(temp,STATUS)
def main():
    os.umask(0o077)
    with (ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        installed=all((ROOT/n).exists() and sha((ROOT/n).read_bytes())==h for n,h in MANIFEST.items())
        if not installed:
            if any(sha((ROOT/n).read_bytes())!=h for n,h in PREVIOUS.items()):
                raise ValueError('unexpected runtime')
            stage=ROOT/('diagnostics-'+RELEASE); stage.mkdir(mode=0o700,exist_ok=True)
            for name,digest in MANIFEST.items():
                data=urllib.request.urlopen('https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/'+RELEASE+'/'+name,timeout=20).read(200001)
                if sha(data)!=digest: raise ValueError('release hash')
                compile(data,name,'exec'); (stage/name).write_bytes(data)
            backup=ROOT/('before-diagnostics-'+RELEASE); backup.mkdir(mode=0o700,exist_ok=True)
            originals={n:(ROOT/n).read_bytes() if (ROOT/n).exists() else None for n in MANIFEST}
            for name,data in originals.items():
                if data is not None: (backup/name).write_bytes(data)
            try:
                for name in MANIFEST:
                    temp=ROOT/(name+'.upgrade'); temp.write_bytes((stage/name).read_bytes()); os.replace(temp,ROOT/name)
            except Exception:
                for name,data in originals.items():
                    if data is not None:
                        temp=ROOT/(name+'.rollback'); temp.write_bytes(data); os.replace(temp,ROOT/name)
                raise
        report({'ok':True,'stage':'diagnostics_installed','release':RELEASE,'runtime_hashes':MANIFEST})
    sys.path.insert(0,str(ROOT))
    runpy.run_path(str(ROOT/'sakura_runner.py'),run_name='__main__')
if __name__=='__main__':
    try: main()
    except Exception as exc:
        report({'ok':False,'stage':'diagnostics_install','error_type':type(exc).__name__})
        sys.exit(1)
