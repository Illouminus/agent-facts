// Снимает логи USDC на Base за окно 30 дней через бесплатные публичные архивные RPC (без ключей).
//   node fetch-logs.mjs window                 -> data/window.json (фиксирует блоки окна)
//   node fetch-logs.mjs in   <addrs.json>      -> Transfer(to ∈ addrs)       raw/logs/in/
//   node fetch-logs.mjs out  <addrs.json>      -> Transfer(from ∈ addrs)     raw/logs/out/
//   node fetch-logs.mjs auth                   -> AuthorizationUsed(authorizer ∈ плательщики из raw/logs/in в том же чанке)
//   node fetch-logs.mjs fund <addrs.json>      -> Transfer(to ∈ addrs) — фондирование плательщиков, raw/logs/fund/
// Суффикс-цифра даёт отдельный набор: in2/out2 + `auth in2` (-> raw/logs/auth2/) — второй каталог (PayAI).
// Чанк = 5000 блоков (~2.8 ч). Перезапуск докачивает только недостающие чанки.
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { gzipSync, gunzipSync } from 'node:zlib';

const DIR = new URL('.', import.meta.url).pathname;
const USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913';
const TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';
const AUTH_USED = '0x98de503528ee59b575ef0c0a2576a82497bfc029a5685b209e9ec333479b10a5'; // AuthorizationUsed(address,bytes32)
const CHUNK = 5000;
const BLOCKS_30D = 30 * 86400 / 2; // Base: блок каждые 2 с
const MAX_TOPICS = Number(process.env.X402_MAX_TOPICS ?? 1600); // blockpi и bloXroute принимают ≥ 9 322 адресов (замер 17.10.2026)

// [url, максимальный диапазон getLogs, параллельность]; лимиты замерены 17.10.2026
const PROVIDERS = [
  { url: 'https://base.public.blockpi.network/v1/rpc/public', span: 5000, conc: 3 },
  { url: 'https://base.rpc.blxrbdn.com', span: 5000, conc: 3 },
  { url: 'https://gateway.tenderly.co/public/base', span: 1000, conc: 3 },
];

const pad = a => '0x' + a.toLowerCase().replace(/^0x/, '').padStart(64, '0');
const hex = n => '0x' + n.toString(16);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function rpc(url, method, params) {
  const r = await fetch(url, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }), signal: AbortSignal.timeout(90000),
  });
  const txt = await r.text();
  let j; try { j = JSON.parse(txt); } catch { throw new Error(`${r.status} ${txt.slice(0, 120)}`); }
  if (j.error) throw new Error(JSON.stringify(j.error).slice(0, 200));
  return j.result;
}

const TOO_MANY = /max results|too many|exceed|limit.*(logs|results)|response size/i;

// диапазон, на который провайдер отвечает «слишком много логов», делится пополам рекурсивно
async function getLogsRange(p, from, to, topics) {
  try {
    return await rpc(p.url, 'eth_getLogs', [{ address: USDC, fromBlock: hex(from), toBlock: hex(to), topics }]);
  } catch (e) {
    if (!TOO_MANY.test(e.message) || from === to) throw e;
    const mid = Math.floor((from + to) / 2);
    return [...await getLogsRange(p, from, mid, topics), ...await getLogsRange(p, mid + 1, to, topics)];
  }
}

async function getLogsOn(p, from, to, topics) {
  const out = [];
  for (let s = from; s <= to; s += p.span) {
    out.push(...await getLogsRange(p, s, Math.min(to, s + p.span - 1), topics));
  }
  return out;
}

// пул: каждый провайдер держит conc слотов; задача при ошибке уходит в очередь заново
async function runPool(tasks, worker) {
  const queue = [...tasks];
  const fails = new Map();
  let done = 0;
  const slots = PROVIDERS.flatMap(p => Array.from({ length: p.conc }, () => p));
  let inFlight = 0;
  await Promise.all(slots.map(async p => {
    // слот не выходит, пока есть задачи в работе: упавшая задача может вернуться в очередь
    while (queue.length || inFlight) {
      if (!queue.length) { await sleep(500); continue; }
      const t = queue.shift();
      inFlight++;
      try {
        await worker(t, p);
        done++;
        if (done % 20 === 0) process.stderr.write(`  ${done}/${tasks.length}\n`);
      } catch (e) {
        const n = (fails.get(t.key) ?? 0) + 1; fails.set(t.key, n);
        process.stderr.write(`  retry ${t.key} on ${p.url.split('/')[2]} (#${n}): ${e.message.slice(0, 120)}\n`);
        if (n > 40) throw new Error(`gave up on ${t.key}`);
        queue.push(t);
        await sleep(1500 * Math.min(n, 8));
      } finally {
        inFlight--;
      }
    }
  }));
}

const compact = l => ({
  b: parseInt(l.blockNumber, 16), ti: parseInt(l.transactionIndex, 16), li: parseInt(l.logIndex, 16),
  tx: l.transactionHash, t: l.topics, d: l.data,
});

function loadWindow() { return JSON.parse(readFileSync(`${DIR}data/window.json`, 'utf8')); }
function chunks(w) {
  const r = [];
  for (let s = w.fromBlock; s <= w.toBlock; s += CHUNK) r.push({ key: String(s), from: s, to: Math.min(w.toBlock, s + CHUNK - 1) });
  return r;
}
export function readChunk(kind, key) {
  return JSON.parse(gunzipSync(readFileSync(`${DIR}raw/logs/${kind}/${key}.json.gz`)).toString());
}

async function cmdWindow() {
  const p = PROVIDERS[0];
  const head = parseInt(await rpc(p.url, 'eth_blockNumber', []), 16) - 100; // запас от реорга
  const toBlock = head, fromBlock = head - BLOCKS_30D + 1;
  const [hb, fb] = await Promise.all([toBlock, fromBlock].map(b => rpc(p.url, 'eth_getBlockByNumber', [hex(b), false])));
  const w = {
    chain: 'base (eip155:8453)', token: USDC, fromBlock, toBlock,
    fromTime: new Date(parseInt(fb.timestamp, 16) * 1000).toISOString(),
    toTime: new Date(parseInt(hb.timestamp, 16) * 1000).toISOString(),
    toTimestamp: parseInt(hb.timestamp, 16), fixedAt: new Date().toISOString(), rpc: p.url,
  };
  mkdirSync(`${DIR}data`, { recursive: true });
  writeFileSync(`${DIR}data/window.json`, JSON.stringify(w, null, 2));
  console.log(w);
}

async function cmdTransfers(kind, addrFile) {
  const w = loadWindow();
  const addrs = JSON.parse(readFileSync(addrFile, 'utf8')).map(a => a.toLowerCase());
  const groups = [];
  for (let i = 0; i < addrs.length; i += MAX_TOPICS) groups.push(addrs.slice(i, i + MAX_TOPICS).map(pad));
  const dir = `${DIR}raw/logs/${kind}`; mkdirSync(dir, { recursive: true });
  const todo = chunks(w).filter(c => !existsSync(`${dir}/${c.key}.json.gz`));
  console.error(`${kind}: ${addrs.length} addrs, ${groups.length} topic groups, ${todo.length} chunks to fetch`);
  await runPool(todo, async (c, p) => {
    const all = [];
    for (const g of groups) {
      const topics = kind.startsWith('out') ? [TRANSFER, g] : [TRANSFER, null, g];
      all.push(...await getLogsOn(p, c.from, c.to, topics));
    }
    writeFileSync(`${dir}/${c.key}.json.gz`, gzipSync(JSON.stringify({ from: c.from, to: c.to, rpc: p.url, logs: all.map(compact) })));
  });
  writeFileSync(`${dir}/_meta.json`, JSON.stringify({ kind, addrFile, addrs: addrs.length, window: w, finishedAt: new Date().toISOString() }, null, 2));
}

async function cmdAuth(src = 'in') {
  const w = loadWindow();
  const dir = `${DIR}raw/logs/auth${src.slice(2)}`; mkdirSync(dir, { recursive: true });
  const todo = chunks(w).filter(c => !existsSync(`${dir}/${c.key}.json.gz`));
  console.error(`auth: ${todo.length} chunks`);
  await runPool(todo, async (c, p) => {
    const inn = readChunk(src, c.key);
    const payers = [...new Set(inn.logs.map(l => '0x' + l.t[1].slice(26)))];
    const all = [];
    for (let i = 0; i < payers.length; i += MAX_TOPICS) {
      all.push(...await getLogsOn(p, c.from, c.to, [AUTH_USED, payers.slice(i, i + MAX_TOPICS).map(pad)]));
    }
    // оставляем только события из транзакций, где есть входящий перевод продавцу
    const txs = new Set(inn.logs.map(l => l.tx));
    writeFileSync(`${dir}/${c.key}.json.gz`, gzipSync(JSON.stringify({ from: c.from, to: c.to, rpc: p.url, payers: payers.length, logs: all.map(compact).filter(l => txs.has(l.tx)) })));
  });
}

const [cmd, arg] = process.argv.slice(2);
if (cmd === 'window') await cmdWindow();
else if (/^(in|out|fund)\d*$/.test(cmd)) await cmdTransfers(cmd, arg);
else if (cmd === 'auth') await cmdAuth(arg);
else console.error('usage: window | in <addrs.json> | out <addrs.json> | auth | fund <addrs.json>');
