// Независимая проверка выгрузки: входящие USDC двум продавцам из выборки за всё окно,
// напрямую с bloXroute диапазонами по 50 000 блоков (мимо fetch-logs.mjs и raw/logs).
// Сравнить с all_in_n / all_in_senders / all_in_usd в data/seller-metrics.csv.
//   node verify-refetch.mjs >> data/verify.txt
import { readFileSync } from 'node:fs';
const DIR = new URL('.', import.meta.url).pathname;
const w = JSON.parse(readFileSync(DIR + 'data/window.json', 'utf8'));
const url = 'https://base.rpc.blxrbdn.com';
const pad = a => '0x' + a.slice(2).padStart(64, '0');
const sellers = ['0x6cab485fc28ec70d3845113b704d4824e4d2b24f', '0x2c871c2b8876dc35e9e19646fda5abf1cd27735f'];
const rpc = async p => {
  for (let i = 0; ; i++) {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getLogs', params: [p] }) });
    const j = await r.json().catch(() => ({}));
    if (j.result) return j.result;
    if (i > 6) throw new Error(JSON.stringify(j).slice(0, 200));
    await new Promise(res => setTimeout(res, 3000 * (i + 1)));
  }
};
const logs = [];
for (let s = w.fromBlock; s <= w.toBlock; s += 50000) {
  const e = Math.min(w.toBlock, s + 49999);
  logs.push(...await rpc({ address: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', fromBlock: '0x' + s.toString(16), toBlock: '0x' + e.toString(16),
    topics: ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', null, sellers.map(pad)] }));
}
for (const s of sellers) {
  const m = logs.filter(l => '0x' + l.topics[2].slice(26) === s);
  console.log(s, 'n', m.length, 'senders', new Set(m.map(l => l.topics[1])).size, 'usd', (m.reduce((a, l) => a + parseInt(l.data, 16), 0) / 1e6).toFixed(4));
}
