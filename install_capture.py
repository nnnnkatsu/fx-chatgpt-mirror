"""Install a narrowly scoped passive response hook, with backup and PHP lint.

No market-data requests. Refuses a proxy different from the reviewed structure.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path("/home/drexworld/fx-mirror")
TARGET = Path("/home/drexworld/www/fx/index.php")
STATUS = Path("/home/drexworld/www/fx-mirror-install.json")
MARKER = b"// ZARJPY passive mirror: persist the existing response only."
HOOK = b"""// ZARJPY passive mirror: persist the existing response only.
if ($pair === 'zarjpy' && $endpoint === 'analysis' && $status === 200) {
    try {
        if (is_readable('/home/drexworld/fx-mirror/capture.php')) {
            @require_once '/home/drexworld/fx-mirror/capture.php';
            fx_mirror_capture_zarjpy($body);
        }
    } catch (\\Throwable $mirrorError) {
        // Mirror failures never change the API response.
    }
}

"""
EXPECTED_CAPTURE_SHA = "668cf09b2dfebd41c6a27539efa9add53bd8278aa009623b725c733ca3db6da3"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_status(value):
    from datetime import datetime, timezone
    value["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    temp = STATUS.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2)+"\n")
    os.chmod(temp,0o644)
    os.replace(temp,STATUS)

def main():
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    php = shutil.which("php")
    if not php:
        raise RuntimeError("PHP CLI unavailable")
    capture = ROOT / "capture.php"
    if digest(capture.read_bytes()) != EXPECTED_CAPTURE_SHA:
        raise ValueError("unexpected capture version")
    def lint(path):
        result = subprocess.run([php, "-l", str(path)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15)
        if result.returncode:
            raise ValueError("PHP lint failed")
    lint(capture)
    original = TARGET.read_bytes()
    if HOOK in original:
        write_status({"ok":True,"stage":"already_installed","proxy_sha256":digest(original)})
        return
    if MARKER in original or len(original) != 17388 or original.count(b"echo $body;") != 1:
        raise ValueError("unreviewed proxy")
    if not original.endswith(b"if ($method === 'HEAD') {\n    exit;\n}\n\necho $body;"):
        raise ValueError("unreviewed proxy tail")
    # This exact insertion is reversible; all existing bytes remain unchanged.
    candidate = original.replace(b"echo $body;", HOOK+b"echo $body;")
    if candidate.replace(HOOK,b"",1) != original:
        raise ValueError("unexpected patch")
    backup = ROOT / ("index.php.before-mirror." + digest(original) + ".bak")
    if not backup.exists():
        backup.write_bytes(original)
        os.chmod(backup,0o600)
    elif backup.read_bytes() != original:
        raise ValueError("backup mismatch")
    staged = ROOT / "index.php.candidate"
    staged.write_bytes(candidate)
    lint(staged)
    # Test capture only against an isolated self-test directory, never real cache.
    testroot = ROOT / "selftest"
    testroot.mkdir(mode=0o700,exist_ok=True)
    isolated = capture.read_text().replace("/home/drexworld/fx-mirror/cache", str(testroot))
    testscript = ROOT / "capture-selftest.php"
    tests = r"""
$input = json_encode(['ok'=>true,'type'=>'analysis','symbol'=>'ZAR/JPY',
'source'=>'Twelve Data','fetched_at_utc'=>'2000-01-01T00:00:00Z','analysis'=>['test'=>true]]);
if (!fx_mirror_capture_zarjpy($input)) { exit(11); }
if (file_get_contents(TESTFILE) !== $input) { exit(12); }
$other = str_replace('ZAR/JPY','USD/JPY',$input);
if (fx_mirror_capture_zarjpy($other)) { exit(13); }
$older = str_replace('2000-01-01','1999-01-01',$input);
if (fx_mirror_capture_zarjpy($older)) { exit(14); }
if (file_get_contents(TESTFILE) !== $input) { exit(15); }
"""
    tests = tests.replace("TESTFILE", repr(str(testroot/"zarjpy-analysis.json")))
    testscript.write_text(isolated+tests)
    check = subprocess.run([php,str(testscript)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    if check.returncode or check.stdout:
        raise ValueError("isolated capture test failed")
    if TARGET.read_bytes() != original:
        raise ValueError("proxy changed during install")
    mode = TARGET.stat().st_mode & 0o777
    os.chmod(staged,mode)
    os.replace(staged,TARGET)
    write_status({"ok":True,"stage":"installed","backup_sha256":digest(original),
                  "proxy_sha256":digest(candidate),"capture_sha256":EXPECTED_CAPTURE_SHA,
                  "php_lint":True,"isolated_capture_test":True,"upstream_requests":0})

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_status({"ok":False,"stage":"install","error_type":type(exc).__name__})
        raise SystemExit(1)
