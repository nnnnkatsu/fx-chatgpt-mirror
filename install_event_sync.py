RELEASE='0e0db60a3581edf4bf269f86a32b15b8df43c734'
MANIFEST={'capture.php': 'aca83970eff3815709cae68b718a2512f676ba92d2ab96623aac90cbcb481d2c', 'sakura_runner.py': '877138a65e6f99d6ccadac1627c876b8661dff69574592e617e8d6a1a65d7b87', 'cache_sync.py': 'f6d022903a40f52deaa6e9af03338b3877f9dd17a70625394f2525c45869f715', 'observed_sync.py': 'cc4bf16e2dce5d50894feb79826d68185241c274d397f60b6f846eaadf694a48'}
PREVIOUS={'capture.php': '0b7c48ad3b3ed312c5d4ce5f0b2ff27bcd0938760b6c45c5ec68b07d7b1b8df3', 'sakura_runner.py': 'e2e83f1f8a54331b68f337a23763350d3f28dfe350d5f4fda33b56168f026cfc', 'cache_sync.py': 'ac7be1983dac905ef0988777beeb08d8c8181514d5c62fd235c163b5767ae84d', 'observed_sync.py': '3093964aa32670af35ecf48a841d6c36498495e9220c9e52184729e6150a00cc'}

import os, sys, json, hashlib, pathlib, urllib.request, subprocess, shutil, fcntl, time
from datetime import datetime, timezone
ROOT=pathlib.Path('/home/drexworld/fx-mirror')
STATUS=pathlib.Path('/home/drexworld/www/fx-mirror-event-install.json')
def sha(data): return hashlib.sha256(data).hexdigest()
def report(value):
    value.update(checked_at_utc=datetime.now(timezone.utc).isoformat(),upstream_requests=0)
    temp=STATUS.with_suffix('.tmp'); temp.write_text(json.dumps(value)); os.chmod(temp,0o644); os.replace(temp,STATUS)
def main():
    os.umask(0o077)
    with (ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        proxy=pathlib.Path('/home/drexworld/www/fx/index.php')
        proxy_hash=sha(proxy.read_bytes())
        installed=all((ROOT/n).exists() and sha((ROOT/n).read_bytes())==h for n,h in MANIFEST.items())
        if not installed:
            if any(sha((ROOT/n).read_bytes())!=h for n,h in PREVIOUS.items()): raise ValueError('unexpected runtime')
            stage=ROOT/('event-'+RELEASE); stage.mkdir(mode=0o700,exist_ok=True)
            for name,digest in MANIFEST.items():
                data=urllib.request.urlopen('https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/'+RELEASE+'/'+name,timeout=20).read(200001)
                if sha(data)!=digest: raise ValueError('release hash')
                if name.endswith('.py'): compile(data,name,'exec')
                (stage/name).write_bytes(data)
            php=shutil.which('php')
            if not php: raise ValueError('PHP unavailable')
            check=subprocess.run([php,'-l',str(stage/'capture.php')],capture_output=True,timeout=15)
            if check.returncode: raise ValueError('PHP lint')
            # Isolated capture and actual detached process, no credentials or market/GitHub HTTP.
            isolated=stage/'selftest'; isolated.mkdir(mode=0o700,exist_ok=True)
            (isolated/'github-credential.json').write_text('{}')
            (isolated/'event-python.txt').write_text(sys.executable)
            (isolated/'sakura_runner.py').write_text("import pathlib,sys\np=pathlib.Path(__file__).parent/(sys.argv[2]+'.event');p.write_text('ok')\n")
            source=(stage/'capture.php').read_text().replace('/home/drexworld/fx-mirror',str(isolated))
            test=r"""
foreach (['zarjpy'=>'ZAR/JPY','usdjpy'=>'USD/JPY','mxnjpy'=>'MXN/JPY'] as $p=>$symbol) {
 $body=json_encode(['ok'=>true,'type'=>'analysis','symbol'=>$symbol,'source'=>'Twelve Data','fetched_at_utc'=>'2000-01-01T00:00:00Z','analysis'=>['test'=>true]], JSON_UNESCAPED_SLASHES);
 if (!fx_mirror_capture($body,$p)) exit(11);
 $file=TESTROOT.'/cache/'.$p.'-analysis.json';
 if (file_get_contents($file)!==$body) exit(12);
 $t=filemtime($file);
 if (!fx_mirror_capture($body,$p)) exit(13);
 if (filemtime($file)!==$t) exit(14);
 if (fx_mirror_capture(str_replace('2000-01-01','1999-01-01',$body),$p)) exit(15);
 if (fx_mirror_capture(str_replace($symbol,'GBP/USD',$body),$p)) exit(16);
}
""".replace('TESTROOT',repr(str(isolated)))
            (stage/'test.php').write_text(source+test)
            check=subprocess.run([php,str(stage/'test.php')],capture_output=True,timeout=15)
            if check.returncode or check.stdout: raise ValueError('capture selftest')
            for attempt in range(30):
                if all((isolated/(p+'.event')).exists() for p in ('USDJPY','ZARJPY','MXNJPY')): break
                time.sleep(0.1)
            else: raise ValueError('background selftest')
            token=os.environ.get('FX_MIRROR_GITHUB_TOKEN')
            if not token: raise ValueError('credential unavailable')
            credential=ROOT/'github-credential.json'
            temp=credential.with_suffix('.tmp'); temp.write_text(json.dumps({'token':token})); os.chmod(temp,0o600); os.replace(temp,credential)
            if credential.stat().st_mode & 0o777 != 0o600: raise ValueError('credential mode')
            (ROOT/'event-python.txt').write_text(sys.executable)
            backup=ROOT/('before-event-'+RELEASE); backup.mkdir(mode=0o700,exist_ok=True)
            originals={n:(ROOT/n).read_bytes() for n in MANIFEST}
            for name,data in originals.items(): (backup/name).write_bytes(data)
            try:
                # Capture is installed last, after its runtime and private configuration.
                for name in ['cache_sync.py','observed_sync.py','sakura_runner.py','capture.php']:
                    temp=ROOT/(name+'.upgrade');temp.write_bytes((stage/name).read_bytes());os.replace(temp,ROOT/name)
                if sha(proxy.read_bytes())!=proxy_hash: raise ValueError('proxy changed')
            except Exception:
                for name,data in originals.items():
                    temp=ROOT/(name+'.rollback');temp.write_bytes(data);os.replace(temp,ROOT/name)
                raise
        report({'ok':True,'stage':'event_sync_installed','release':RELEASE,'runtime_hashes':MANIFEST,'proxy_sha256':proxy_hash,'proxy_unchanged':True,'php_lint':True,'isolated_background_test':True,'credential_mode':'0600','cron_seconds':120})
    sys.path.insert(0,str(ROOT))
    import sakura_runner
    sakura_runner.run()
if __name__=='__main__':
    try: main()
    except Exception as exc:
        allowed={'unexpected runtime','release hash','PHP unavailable','PHP lint','capture selftest','background selftest','credential unavailable','credential mode','proxy changed'}
        report({'ok':False,'stage':'event_install_failed','error_type':type(exc).__name__,'reason':str(exc) if str(exc) in allowed else 'other'})
        sys.exit(1)
