<?php
// Optional sidecar hook, called only with an ALREADY obtained response body.
// No market HTTP, headers or output. Changed cache launches a passive background publisher.
// Integration must be checked against the live proxy before installation.
function fx_mirror_capture_zarjpy($body) { return fx_mirror_capture($body, "zarjpy"); }
function fx_mirror_capture($body, $pair) {
    $symbols = ["zarjpy"=>"ZAR/JPY", "usdjpy"=>"USD/JPY", "mxnjpy"=>"MXN/JPY"];
    if (!isset($symbols[$pair])) { return false; }
    if (!is_string($body) || strlen($body) > 1000000) { return false; }
    $data = json_decode($body, true);
    if (!is_array($data) || ($data['ok'] ?? false) !== true ||
        ($data['type'] ?? '') !== 'analysis' || ($data['symbol'] ?? '') !== $symbols[$pair] ||
        ($data['source'] ?? '') !== 'Twelve Data' || empty($data['fetched_at_utc']) ||
        !isset($data['analysis'])) { return false; }
    $fetched = strtotime($data['fetched_at_utc']);
    if ($fetched === false) { return false; }
    $root = '/home/drexworld/fx-mirror/cache';
    $previousMask = umask(0077);
    $lock = false;
    $temp = false;
    $changed = false;
    try {
        if (!is_dir($root) && !@mkdir($root, 0700, true)) { return false; }
        $lock = @fopen($root . '/capture.lock', 'a');
        if (!$lock || !@flock($lock, LOCK_EX | LOCK_NB)) { return false; }
        $target = $root . '/' . $pair . '-analysis.json';
        if (is_file($target)) {
            $oldBody = @file_get_contents($target);
            if ($oldBody === $body) { return true; }
            $old = json_decode($oldBody === false ? '' : $oldBody, true);
            if (is_array($old) && isset($old['fetched_at_utc']) &&
                strtotime($old['fetched_at_utc']) > $fetched) { return false; }
        }
        $temp = @tempnam($root, '.analysis-');
        if ($temp === false || @file_put_contents($temp, $body) !== strlen($body)) { return false; }
        @chmod($temp, 0600);
        if (!@rename($temp, $target)) { return false; }
        $temp = false;
        $changed = true;
        return true;
    } catch (Throwable $error) {
        // Deliberately do not log response bodies or exception messages.
        return false;
    } finally {
        if ($temp !== false) { @unlink($temp); }
        if ($lock !== false) { @flock($lock, LOCK_UN); @fclose($lock); }
        umask($previousMask);
        if ($changed) { fx_mirror_notify($pair); }
    }
}

// A finite, detached job. No credential or response body is passed to the shell.
// If exec is unavailable or publication fails, the existing 2-minute cron retries.
function fx_mirror_notify($pair) {
    try {
        if (!in_array($pair, ['zarjpy', 'usdjpy', 'mxnjpy'], true)) { return; }
        $root = '/home/drexworld/fx-mirror';
        if (!function_exists('exec') || !is_readable($root . '/github-credential.json') ||
            !is_readable($root . '/event-python.txt')) { return; }
        $python = trim(file_get_contents($root . '/event-python.txt'));
        if ($python === '' || $python[0] !== '/' || !is_executable($python)) { return; }
        $command = escapeshellarg($python) . ' ' . escapeshellarg($root . '/sakura_runner.py') .
            ' --event ' . escapeshellarg(strtoupper($pair)) . ' </dev/null >/dev/null 2>&1 &';
        @exec($command);
    } catch (Throwable $error) {
        // The API response is independent of mirror availability.
    }
}
