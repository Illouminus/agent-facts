// Точечные проверки для отчёта -> data/probes.json:
//  1) разбор одной x402-транзакции (вызов, отправитель, события) — проверка определения платежа;
//  2) nonce / код / баланс USDC у 10 самых «широких» плательщиков из data/payers.csv (обходчики);
//  3) nonce / код у главного пополнителя для топ-15 мелких продавцов (если есть фонд-проход).
import { readFileSync, writeFileSync } from 'node:fs';

const DIR = new URL('.', import.meta.url).pathname;
const URL_ = 'https://base.rpc.blxrbdn.com';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const rpc = async (method, params) => {
  for (let i = 0; ; i++) {
    const r = await fetch(URL_, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) });
    const j = await r.json().catch(() => ({}));
    if (j.result !== undefined) return j.result;
    if (i > 5) throw new Error(`${method} failed: ${JSON.stringify(j).slice(0, 200)}`);
    await new Promise(res => setTimeout(res, 2000 * (i + 1)));
  }
};
const info = async a => ({
  address: a,
  codeBytes: ((await rpc('eth_getCode', [a, 'latest'])).length - 2) / 2,
  nonce: parseInt(await rpc('eth_getTransactionCount', [a, 'latest']), 16),
  usdc: parseInt(await rpc('eth_call', [{ to: USDC, data: '0x70a08231' + a.slice(2).padStart(64, '0') }, 'latest']), 16) / 1e6,
});
// CSV с кавычками (описания содержат запятые)
const csv = f => {
  const text = readFileSync(DIR + f, 'utf8'), rows = [[]];
  let cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c;
    } else if (c === '"') q = true;
    else if (c === ',') { rows.at(-1).push(cell); cell = ''; }
    else if (c === '\n') { rows.at(-1).push(cell.replace(/\r$/, '')); cell = ''; rows.push([]); }
    else cell += c;
  }
  if (cell || rows.at(-1).length) rows.at(-1).push(cell); else rows.pop();
  const [h, ...body] = rows;
  return body.map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
};

const TX = '0xd2b5681c3f5f607b287c1856eec38cc743efd89c8e5b4894d8cce26668d0b8f5';
const [tx, rc] = await Promise.all([rpc('eth_getTransactionByHash', [TX]), rpc('eth_getTransactionReceipt', [TX])]);
const sampleTx = {
  hash: TX, from: tx.from, to: tx.to, selector: tx.input.slice(0, 10),
  logs: rc.logs.map(l => ({ address: l.address, topic0: l.topics[0] })),
};

const payers = csv('data/payers.csv').slice(0, 10);
const crawlers = [];
for (const p of payers) crawlers.push({ ...(await info(p.payer)), sellers_paid_x402: +p.sellers_paid_x402, x402_tx: +p.x402_tx });

const top = csv('data/seller-metrics.csv').filter(r => r.class === 'small' && r.top_funder).slice(0, 15);
const funders = [];
for (const r of top) funders.push({ seller: r.payTo, domain: r.primary_domain, top_funder_payers: +r.top_funder_payers, foreign_payers: +r.foreign_payers, ...(await info(r.top_funder)) });

writeFileSync(DIR + 'data/probes.json', JSON.stringify({ at: new Date().toISOString(), rpc: URL_, sampleTx, crawlers, funders }, null, 1));
console.log(JSON.stringify({ sampleTx, crawlers: crawlers.slice(0, 4) }, null, 1));
