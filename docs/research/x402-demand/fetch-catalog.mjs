// Выгрузка каталога Bazaar (discovery-эндпоинт фасилитатора) целиком.
//   node fetch-catalog.mjs            -> Coinbase CDP: raw/catalog/, data/catalog-items.jsonl
//   node fetch-catalog.mjs payai      -> PayAI:        raw/catalog-payai/, data/catalog-payai-items.jsonl
import { mkdirSync, writeFileSync, createWriteStream } from 'node:fs';
import { gzipSync } from 'node:zlib';

const SOURCES = {
  cdp: { url: 'https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources', raw: 'catalog', out: 'catalog' },
  payai: { url: 'https://facilitator.payai.network/discovery/resources', raw: 'catalog-payai', out: 'catalog-payai' },
};
const SRC = SOURCES[process.argv[2] ?? 'cdp'];
const BASE = SRC.url;
const LIMIT = 1000;
const dir = new URL('.', import.meta.url).pathname;
mkdirSync(`${dir}raw/${SRC.raw}`, { recursive: true });
mkdirSync(`${dir}data`, { recursive: true });

const out = createWriteStream(`${dir}data/${SRC.out}-items.jsonl`);
const fetchedAt = new Date().toISOString();
let offset = 0, total = Infinity, n = 0;
while (offset < total) {
  const url = `${BASE}?limit=${LIMIT}&offset=${offset}`;
  let body;
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(url);
    if (r.ok) { body = await r.text(); break; }
    if (attempt >= 5) throw new Error(`${url} -> ${r.status}`);
    await new Promise(res => setTimeout(res, 2000 * attempt));
  }
  writeFileSync(`${dir}raw/${SRC.raw}/page-${String(offset).padStart(6, '0')}.json.gz`, gzipSync(body));
  const j = JSON.parse(body);
  total = j.pagination.total;
  for (const it of j.items) {
    out.write(JSON.stringify({
      resource: it.resource,
      serviceName: it.serviceName ?? null,
      description: (it.description ?? it.metadata?.description ?? '').slice(0, 300),
      tags: it.tags ?? [],
      x402Version: it.x402Version,
      lastUpdated: it.lastUpdated,
      quality: it.quality ?? null,
      accepts: (it.accepts ?? []).map(a => ({
        network: a.network, payTo: a.payTo, asset: a.asset,
        amount: a.amount ?? a.maxAmountRequired ?? null, scheme: a.scheme,
      })),
    }) + '\n');
    n++;
  }
  process.stderr.write(`offset ${offset} -> ${j.items.length} items (total ${total})\n`);
  if (j.items.length === 0) break;
  offset += LIMIT;
}
out.end();
writeFileSync(`${dir}data/${SRC.out}-meta.json`, JSON.stringify({ source: BASE, fetchedAt, total, itemsWritten: n }, null, 2));
console.log(`done: ${n} items, fetchedAt ${fetchedAt}`);
