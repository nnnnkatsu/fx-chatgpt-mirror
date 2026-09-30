import fs from 'node:fs';import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('./worker.js',import.meta.url),'utf8').replace('import { DurableObject } from "cloudflare:workers";','class DurableObject {}');
const {scheduledPairs}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const at=s=>scheduledPairs(Date.parse(s+'+09:00'));
assert.deepEqual(at('2026-09-28T00:14:00'),[]);assert.deepEqual(at('2026-09-29T00:14:00'),['mxnjpy']);assert.deepEqual(at('2026-10-03T00:39:00'),['zarjpy']);assert.deepEqual(at('2026-10-03T08:14:00'),[]);assert.deepEqual(at('2026-10-04T00:39:00'),[]);assert.deepEqual(at('2026-09-30T11:57:00'),[]);assert.deepEqual(at('2026-09-30T12:14:00'),['mxnjpy']);assert.deepEqual(at('2026-09-30T23:04:00'),['usdjpy']);
let counts={};for(let i=0;i<7*1440;i++)for(const p of scheduledPairs(Date.parse('2026-09-28T00:00:00+09:00')+i*60000))counts[p]=(counts[p]||0)+1;
assert.deepEqual(counts,{usdjpy:80,mxnjpy:25,zarjpy:25});console.log('PASS weekly 80/25/25, JST midnight rollover, weekend exclusion, no old MXN slots');
