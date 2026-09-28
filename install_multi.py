RELEASE = 'ca08ec51e92e7f1718982abcc9a97026c47e50dc'
MANIFEST = {'mirror.py': '84186ab0e36545f4a030dcfbb6d6225d05f25d212b3f07558a3f6989dda2f3ce', 'cache_sync.py': '8e969f0ba0b1cf3a3fc794192b670605baf757dd86739a734503cddbff8b07b5', 'capture.php': '0b7c48ad3b3ed312c5d4ce5f0b2ff27bcd0938760b6c45c5ec68b07d7b1b8df3', 'sakura_runner.py': 'a102e09180ed3dbc185803650064c186e9166d579fbfbf50db71c5bf7dbed744'}
OLD_HOOK = b"// ZARJPY passive mirror: persist the existing response only.\nif ($pair === 'zarjpy' && $endpoint === 'analysis' && $status === 200) {\n    try {\n        if (is_readable('/home/drexworld/fx-mirror/capture.php')) {\n            @require_once '/home/drexworld/fx-mirror/capture.php';\n            fx_mirror_capture_zarjpy($body);\n        }\n    } catch (\\Throwable $mirrorError) {\n        // Mirror failures never change the API response.\n    }\n}\n\n"
NEW_HOOK = b"// Multi-pair passive mirror: persist the existing response only.\nif (in_array($pair, ['zarjpy', 'usdjpy', 'mxnjpy'], true) && $endpoint === 'analysis' && $status === 200) {\n    try {\n        if (is_readable('/home/drexworld/fx-mirror/capture.php')) {\n            @require_once '/home/drexworld/fx-mirror/capture.php';\n            fx_mirror_capture($body, $pair);\n        }\n    } catch (\\Throwable $mirrorError) {\n        // Mirror failures never change the API response.\n    }\n}\n\n"

import os, sys, json, hashlib, pathlib, urllib.request, subprocess, shutil, fcntl
from datetime import datetime, timezone
ROOT=pathlib.Path('/home/drexworld/fx-mirror')
TARGET=pathlib.Path('/home/drexworld/www/fx/index.php')
STATUS=pathlib.Path('/home/drexworld/www/fx-mirror-install.json')
def sha(data): return hashlib.sha256(data).hexdigest()
def status(value):
    value['checked_at_utc']=datetime.now(timezone.utc).isoformat()
    temp=STATUS.with_suffix('.tmp'); temp.write_text(json.dumps(value)); os.chmod(temp,0o644); os.replace(temp,STATUS)
def main():
    os.umask(0o077)
    with (ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        original=TARGET.read_bytes()
        if NEW_HOOK in original and all((ROOT/n).exists() and sha((ROOT/n).read_bytes())==h for n,h in MANIFEST.items()):
            return
        if sha(original)!='b588f0ae4ca12b8fcb36ed0332fc85b90032cae7952be0063f51a3d30dae6815' or original.count(OLD_HOOK)!=1:
            raise ValueError('unreviewed proxy')
        staged=ROOT/('release-'+RELEASE); staged.mkdir(mode=0o700,exist_ok=True)
        for name,digest in MANIFEST.items():
            data=urllib.request.urlopen('https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/'+RELEASE+'/'+name,timeout=20).read(200001)
            if sha(data)!=digest: raise ValueError('release hash')
            (staged/name).write_bytes(data)
            if name.endswith('.py'): compile(data,str(staged/name),'exec')
        php=shutil.which('php')
        if not php: raise ValueError('PHP unavailable')
        candidate=original.replace(OLD_HOOK,NEW_HOOK)
        (staged/'index.php').write_bytes(candidate)
        for name in ('capture.php','index.php'):
            result=subprocess.run([php,'-l',str(staged/name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
            if result.returncode: raise ValueError('PHP lint')
        testroot=staged/'selftest'; testroot.mkdir(mode=0o700,exist_ok=True)
        source=(staged/'capture.php').read_text().replace('/home/drexworld/fx-mirror/cache',str(testroot))
        test=r"""
foreach (['zarjpy'=>'ZAR/JPY','usdjpy'=>'USD/JPY','mxnjpy'=>'MXN/JPY'] as $p=>$symbol) {
 $body=json_encode(['ok'=>true,'type'=>'analysis','symbol'=>$symbol,'source'=>'Twelve Data','fetched_at_utc'=>'2000-01-01T00:00:00Z','analysis'=>['test'=>true]], JSON_UNESCAPED_SLASHES);
 if (!fx_mirror_capture($body,$p)) exit(11);
 if (file_get_contents(TESTROOT.'/'.$p.'-analysis.json') !== $body) exit(12);
 if (fx_mirror_capture(str_replace($symbol,'GBP/USD',$body),$p)) exit(13);
 if (fx_mirror_capture(str_replace('2000-01-01','1999-01-01',$body),$p)) exit(14);
}
""".replace('TESTROOT',repr(str(testroot)))
        (staged/'selftest.php').write_text(source+test)
        result=subprocess.run([php,str(staged/'selftest.php')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        if result.returncode or result.stdout: raise ValueError('capture selftest')
        backup=ROOT/('before-'+RELEASE); backup.mkdir(mode=0o700,exist_ok=True)
        snapshots={n:(ROOT/n).read_bytes() for n in MANIFEST}
        for name,data in snapshots.items(): (backup/name).write_bytes(data)
        (backup/'index.php').write_bytes(original)
        if TARGET.read_bytes()!=original: raise ValueError('proxy changed')
        try:
            for name in MANIFEST:
                temp=ROOT/(name+'.upgrade'); temp.write_bytes((staged/name).read_bytes()); os.replace(temp,ROOT/name)
            temp=TARGET.with_name('index.php.mirror-upgrade'); temp.write_bytes(candidate); os.chmod(temp,TARGET.stat().st_mode & 0o777); os.replace(temp,TARGET)
        except Exception:
            for name,data in snapshots.items():
                temp=ROOT/(name+'.rollback'); temp.write_bytes(data); os.replace(temp,ROOT/name)
            raise
        status({'ok':True,'stage':'multi_pair_installed','release':RELEASE,'pairs':['ZARJPY','USDJPY','MXNJPY'],'proxy_sha256':sha(candidate),'backup_sha256':sha(original),'php_lint':True,'isolated_capture_test':True,'upstream_requests':0})
if __name__=='__main__':
    try: main()
    except Exception as exc:
        status({'ok':False,'stage':'multi_pair_install','error_type':type(exc).__name__,'reason':str(exc) if str(exc) in ('unreviewed proxy','release hash','PHP unavailable','PHP lint','capture selftest','proxy changed') else 'other','upstream_requests':0})
        sys.exit(1)
