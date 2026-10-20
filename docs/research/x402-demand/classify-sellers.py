"""Свод двух каталогов Bazaar по адресу payTo на Base и разметка класса продавца.

  python3 -I classify-sellers.py  -> data/sellers.csv, data/sample-small.json

Класс:
  big       — хотя бы один ресурс на домене известного бренда (список BIG ниже);
  platform  — основной домен принадлежит перепродавцу чужих API / инфраструктуре x402 (PLATFORM, семейство stable*.dev);
  small     — всё остальное (мелкие независимые API данных и инструментов).
Разметка по доменам — эвристика; её пределы описаны в отчёте.
"""
import csv, json, random, re, statistics, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent
BASE_NETS = {'eip155:8453', 'base'}

BIG = {
    'coingecko.com': 'CoinGecko', 'quicknode.com': 'QuickNode', 'exa.ai': 'Exa', 'nansen.ai': 'Nansen',
    'glassnode.com': 'Glassnode', 'chain.link': 'Chainlink', 'pocket.network': 'Pocket Network',
    'apify.com': 'Apify', 'bitrefill.com': 'Bitrefill', 'alchemy.com': 'Alchemy', 'messari.io': 'Messari',
    'browserbase.com': 'Browserbase', 'tavily.com': 'Tavily', 'coinmarketcap.com': 'CoinMarketCap',
    'zerion.io': 'Zerion', '0x.org': '0x', 'blockchain.info': 'Blockchain.com', 'heurist.xyz': 'Heurist',
    'cloudflare.com': 'Cloudflare', 'coinbase.com': 'Coinbase', 'stripe.com': 'Stripe',
}
# перепродавцы чужих API под одним кошельком и компании инфраструктуры x402 (Merit Systems — авторы x402scan)
PLATFORM = {
    'stableenrich.dev', 'stabletravel.dev', 'stableupload.dev', 'stableapify.dev', 'enrichx402.com',
    'x402scan.com', 'paywithlocus.com', 'paysponge.com', 'payai.network',
}
# семейство stable*.dev (Merit Systems): часть подтверждена превью-деплоями *-merit-systems.vercel.app, остальные — по шаблону имени
STABLE_DEV = re.compile(r'^(www\.)?stable[-a-z]*\.dev$')
# хостинги, где «регистрируемый домен» на уровень глубже
HOSTING = ('workers.dev', 'vercel.app', 'up.railway.app', 'onrender.com', 'on.aws', 'pythonanywhere.com',
           'a.run.app', 'netlify.app', 'herokuapp.com', 'fly.dev', 'pages.dev', 'deno.dev', 'replit.app',
           'github.io', 'ngrok-free.app', 'trycloudflare.com', 'railway.app', 'web.app', 'azurewebsites.net')


# двухуровневые публичные суффиксы, встреченные в каталогах
SECOND_LEVEL = {'co.uk', 'org.uk', 'ac.uk', 'com.mx', 'com.br', 'com.au', 'net.au', 'com.tr', 'net.co', 'co.jp', 'co.kr',
                'co.in', 'co.za', 'com.sg', 'co.nz', 'com.cn', 'com.hk', 'com.ar', 'co.id', 'com.my'}


def reg_domain(host):
    host = (host or '').lower()
    if '.'.join(host.split('.')[-2:]) in SECOND_LEVEL:
        return '.'.join(host.split('.')[-3:])
    for h in HOSTING:
        if host.endswith('.' + h):
            return '.'.join(host.split('.')[-(len(h.split('.')) + 1):])
    return '.'.join(host.split('.')[-2:])


def main():
    recs = defaultdict(lambda: {'domains': Counter(), 'names': Counter(), 'res': {}, 'src': set()})
    for src, f in [('cdp', 'data/catalog-items.jsonl'), ('payai', 'data/catalog-payai-items.jsonl')]:
        for line in open(D / f):
            it = json.loads(line)
            for a in it['accepts']:
                pt = str(a.get('payTo') or '')
                if a['network'] not in BASE_NETS or not pt.startswith('0x') or len(pt) != 42:
                    continue
                r = recs[pt.lower()]
                r['src'].add(src)
                if it['resource'] in r['res']:
                    continue
                q = it.get('quality') or {}
                try:
                    price = int(a['amount']) / 1e6 if a.get('amount') not in (None, '') else None
                except ValueError:
                    price = None
                r['res'][it['resource']] = {
                    'price': price, 'calls': q.get('l30DaysTotalCalls') or 0,
                    'payers': q.get('l30DaysUniquePayers') or 0, 'desc': it.get('description') or '',
                }
                r['domains'][reg_domain(urllib.parse.urlparse(it['resource']).hostname)] += 1
                if it.get('serviceName'):
                    r['names'][it['serviceName']] += 1

    rows = []
    for addr, r in recs.items():
        primary = r['domains'].most_common(1)[0][0]
        brand = next((BIG[d] for d in r['domains'] if d in BIG), None)
        merit = any('merit-systems' in d for d in r['domains']) or bool(STABLE_DEV.match(primary))
        cls = 'big' if brand else 'platform' if (primary in PLATFORM or merit) else 'small'
        prices = [x['price'] for x in r['res'].values() if x['price'] is not None]
        descs = [x['desc'] for x in r['res'].values() if x['desc']]
        rows.append({
            'payTo': addr, 'class': cls, 'brand': brand or '', 'primary_domain': primary,
            'n_domains': len(r['domains']), 'n_resources': len(r['res']),
            'service_names': ' | '.join(n for n, _ in r['names'].most_common(2)),
            'price_min_usd': min(prices) if prices else '', 'price_median_usd': statistics.median(prices) if prices else '',
            'price_max_usd': max(prices) if prices else '',
            'description': (descs[0] if descs else '').replace('\n', ' ')[:160],
            'catalogs': '+'.join(sorted(r['src'])),
            'cdp_claimed_calls_30d': sum(x['calls'] for x in r['res'].values()),
            'cdp_claimed_max_unique_payers_30d': max((x['payers'] for x in r['res'].values()), default=0),
        })
    rows.sort(key=lambda x: (x['class'], x['payTo']))
    with open(D / 'data/sellers.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    small = sorted(x['payTo'] for x in rows if x['class'] == 'small')
    sample = random.Random(402).sample(small, 25)
    json.dump({'seed': 402, 'n_population': len(small), 'sample': sample}, open(D / 'data/sample-small.json', 'w'), indent=1)
    print(Counter(x['class'] for x in rows), 'sample', len(sample))
    for b in sorted({x['brand'] for x in rows if x['brand']}):
        print('  big:', b, sum(1 for x in rows if x['brand'] == b), 'addr')


if __name__ == '__main__':
    main()
