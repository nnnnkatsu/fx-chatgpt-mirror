import fs from 'node:fs';import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('./worker.js',import.meta.url),'utf8').replace('import { DurableObject } from "cloudflare:workers";','class DurableObject {}');
const {scheduledPairs}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const at=s=>scheduledPairs(Date.parse(s+'+09:00'));
for(const m of ['09','13','17'])assert.deepEqual(at('2026-10-02T12:'+m+':00'),['mxnjpy']);
for(const m of ['34','38','42'])assert.deepEqual(at('2026-10-02T12:'+m+':00'),['zarjpy']);
assert.deepEqual(at('2026-10-02T11:59:00'),['usdjpy']);
assert.deepEqual(at('2026-10-02T12:03:00'),['usdjpy']);
assert.deepEqual(at('2026-10-02T12:07:00'),['usdjpy']);
assert.deepEqual(at('2026-09-28T07:59:00'),['usdjpy']);
assert.deepEqual(at('2026-09-28T00:09:00'),[]);
assert.deepEqual(at('2026-09-29T00:09:00'),['mxnjpy']);
assert.deepEqual(at('2026-10-03T00:42:00'),['zarjpy']);
assert.deepEqual(at('2026-10-03T08:09:00'),[]);
assert.deepEqual(at('2026-10-04T00:34:00'),[]);
let counts={}, events=[];
for(let i=0;i<14*1440;i++) {
 const ms=Date.parse('2026-09-28T00:00:00+09:00')+i*60000;
 const ps=scheduledPairs(ms); assert.ok(ps.length<=1,'no simultaneous pair batch');
 for(const p of ps){if(i<7*1440)counts[p]=(counts[p]||0)+1;events.push(ms);}
}
assert.deepEqual(counts,{usdjpy:240,mxnjpy:75,zarjpy:75});
let max=0;for(let i=0;i<events.length;i++){
 if(i)assert.ok(events[i]-events[i-1]>=120000,'at least two minutes between calls');
 max=Math.max(max,events.filter(t=>t<=events[i]&&t>events[i]-86400000).length*7);
}
assert.equal(max,546);assert.ok(max<600);
const cfg=fs.readFileSync(new URL('./wrangler.toml',import.meta.url),'utf8');
assert.ok(cfg.includes('59,3,7 * * * *'));assert.ok(cfg.includes('9,13,17 3,7,11,15,23 * * *'));assert.ok(cfg.includes('34,38,42 3,7,11,15,23 * * *'));
console.log('PASS three slots/check, midnight/weekends, no overlap, >=120s separation, max rolling 24h scheduled credits=546');
