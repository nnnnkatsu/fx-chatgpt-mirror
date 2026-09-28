<?php
// Optional sidecar hook, called only with an ALREADY obtained response body.
// No HTTP, no GitHub calls, no headers, no output, and no changes to API routes.
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
    try {
        if (!is_dir($root) && !@mkdir($root, 0700, true)) { return false; }
        $lock = @fopen($root . '/capture.lock', 'a');
        if (!$lock || !@flock($lock, LOCK_EX | LOCK_NB)) { return false; }
        $target = $root . '/' . $pair . '-analysis.json';
        if (is_file($target)) {
            $oldBody = @file_get_contents($target);
            $old = json_decode($oldBody === false ? '' : $oldBody, true);
            if (is_array($old) && isset($old['fetched_at_utc']) &&
                strtotime($old['fetched_at_utc']) > $fetched) { return false; }
        }
        $temp = @tempnam($root, '.analysis-');
        if ($temp === false || @file_put_contents($temp, $body) !== strlen($body)) { return false; }
        @chmod($temp, 0600);
        if (!@rename($temp, $target)) { return false; }
        $temp = false;
        return true;
    } catch (Throwable $error) {
        // Deliberately do not log response bodies or exception messages.
        return false;
    } finally {
        if ($temp !== false) { @unlink($temp); }
        if ($lock !== false) { @flock($lock, LOCK_UN); @fclose($lock); }
        umask($previousMask);
    }
}
