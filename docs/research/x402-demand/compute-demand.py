"""Метрики спроса по каждому продавцу из сырых логов Base (raw/logs/*) и разметки (data/sellers.csv).

  python3 -I compute-demand.py [--crawler N]   (N — порог обходчика, по умолчанию 20 продавцов)
  -> data/seller-metrics.csv, data/payers.csv, data/summary.json  (с --crawler N — файлы с суффиксом)

Платёж x402 = входящий Transfer USDC продавцу, в той же транзакции есть AuthorizationUsed(authorizer = плательщик),
т. е. перевод исполнен через EIP-3009 transferWithAuthorization (схема exact x402 по умолчанию для USDC).
«Чужой» плательщик = плательщик x402 минус фильтры шума:
  self        плательщик == продавец;
  funded      продавец сам переводил USDC этому плательщику в окне (фондирование / круговой платёж);
  same_owner  плательщик — payTo другого продавца с тем же основным доменом (кошелёк того же владельца);
  crawler     плательщик в окне платил ≥ N разным продавцам каталога (обходчик / накрутка лидерборда).
«Кластеры» (основная метрика) = чужие плательщики, где сибилы схлопнуты: плательщики продавца S, у которых
первый пополнитель USDC в окне — один адрес F, склеиваются в один, если таких плательщиков у S ≥ 3 и
  либо ≥ 80 % всех чужих плательщиков, пополненных F, платят именно S (F существует ради S),
  либо ≥ 50 % платят S и ≥ 50 % первых пополнений от F — одна и та же сумма (раздача, а не вывод с биржи).
"""
import csv, glob, gzip, json, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent
CRAWLER = int(sys.argv[sys.argv.index('--crawler') + 1]) if '--crawler' in sys.argv else 20
OUT_SUFFIX = '' if CRAWLER == 20 else f'-crawler{CRAWLER}'
ZERO = '0x' + '0' * 40
SYBIL_MIN, SYBIL_CONC_ALONE, SYBIL_CONC, SYBIL_SAME_AMOUNT = 3, 0.8, 0.5, 0.5


def addr(topic):
    return '0x' + topic[26:]


def load(kind):
    rows = []
    for f in sorted(glob.glob(str(D / f'raw/logs/{kind}/*.json.gz'))):
        rows.extend(json.loads(gzip.open(f).read())['logs'])
    return rows


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else None


def main():
    w = json.load(open(D / 'data/window.json'))
    ts = lambda b: w['toTimestamp'] - 2 * (w['toBlock'] - b)
    sellers = {r['payTo']: r for r in csv.DictReader(open(D / 'data/sellers.csv'))}
    domain_of = {a: r['primary_domain'] for a, r in sellers.items()}
    owners = defaultdict(set)
    for a, dmn in domain_of.items():
        owners[dmn].add(a)

    inc = load('in') + load('in2')
    auth = {(l['tx'], addr(l['t'][1])) for l in load('auth') + load('auth2')}
    seller_paid = defaultdict(set)  # продавец -> кому он сам переводил USDC в окне
    for l in load('out') + load('out2'):
        seller_paid[addr(l['t'][1])].add(addr(l['t'][2]))

    seen = set()
    pays = []  # (seller, payer, usd, block, is3009)
    for l in inc:
        k = (l['tx'], l['li'])
        if k in seen:
            continue
        seen.add(k)
        payer, seller = addr(l['t'][1]), addr(l['t'][2])
        if payer == ZERO or seller not in sellers:
            continue
        pays.append((seller, payer, int(l['d'], 16) / 1e6, l['b'], (l['tx'], payer) in auth))

    # ширина плательщика: скольким продавцам каталога он платил через x402 в окне
    breadth = defaultdict(set)
    ptx = Counter()
    for s, p, _, _, x in pays:
        if x:
            breadth[p].add(s); ptx[p] += 1

    # первый пополнитель USDC каждого плательщика в окне и сумма этого пополнения (raw/logs/fund)
    funder, fund_amt = {}, {}
    fund_logs = load('fund') + load('fund2')
    for l in sorted(fund_logs, key=lambda l: (l['b'], l['li'])):
        to, frm = addr(l['t'][2]), addr(l['t'][1])
        if to not in funder and frm != ZERO:
            funder[to], fund_amt[to] = frm, int(l['d'], 16)
    have_fund = bool(fund_logs)

    by_seller = defaultdict(list)
    for p in pays:
        by_seller[p[0]].append(p)

    # проход 1: причины отсева и чужие плательщики по каждому продавцу
    per = {}
    for s in sellers:
        x = [p for p in by_seller[s] if p[4]]
        reasons = {}
        for _, p, *_ in x:
            if p in reasons:
                continue
            if p == s:
                reasons[p] = 'self'
            elif p in seller_paid[s]:
                reasons[p] = 'funded'
            elif p in owners[domain_of[s]]:
                reasons[p] = 'same_owner'
            elif len(breadth[p]) >= CRAWLER:
                reasons[p] = 'crawler'
            else:
                reasons[p] = None
        foreign = [p for p in x if reasons[p[1]] is None]
        per[s] = (x, reasons, foreign, {p[1] for p in foreign})

    # кому из чужих плательщиков пополнял каждый адрес F
    funded_by = defaultdict(set)
    for s, (_, _, _, fp) in per.items():
        for p in fp:
            if p in funder:
                funded_by[funder[p]].add(p)

    rows = []
    collapsed = {}
    for s, meta in sellers.items():
        mine = by_seller[s]
        x, reasons, foreign, fpayers = per[s]
        # сибилы: схлопнуть плательщиков S с общим «раздающим» пополнителем
        groups = defaultdict(set)
        for p in fpayers:
            if p in funder:
                groups[funder[p]].add(p)
        sybil_funders = {}
        for F, ps in groups.items():
            same = Counter(fund_amt[p] for p in ps).most_common(1)[0][1] / len(ps)
            conc = len(ps) / len(funded_by[F])
            if len(ps) >= SYBIL_MIN and (conc >= SYBIL_CONC_ALONE or (conc >= SYBIL_CONC and same >= SYBIL_SAME_AMOUNT)):
                sybil_funders[F] = len(ps)
        clusters = {funder[p] if funder.get(p) in sybil_funders else p for p in fpayers}
        collapsed[s] = {p for p in fpayers if funder.get(p) in sybil_funders}
        top_f, top_n = (groups and max(((F, len(ps)) for F, ps in groups.items()), key=lambda t: t[1])) or ('', 0)

        days_by_payer = defaultdict(set)
        for _, p, _, b, _ in foreign:
            days_by_payer[p].add(ts(b) // 86400)
        repeat = {p for p, d in days_by_payer.items() if len(d) >= 2}
        # всплеск: доля x402-платежей в самом плотном часе (900 блоков по 2 с ≈ 30 мин в каждую сторону)
        bl = sorted(p[3] for p in x)
        burst, j = 0, 0
        for i in range(len(bl)):
            while bl[i] - bl[j] > 1800:
                j += 1
            burst = max(burst, i - j + 1)
        rc = Counter(reasons.values())
        rows.append({
            'payTo': s, 'class': meta['class'], 'brand': meta['brand'], 'primary_domain': meta['primary_domain'],
            'service_names': meta['service_names'], 'n_resources': meta['n_resources'],
            'price_median_usd': meta['price_median_usd'], 'description': meta['description'],
            'all_in_n': len(mine), 'all_in_senders': len({p[1] for p in mine}), 'all_in_usd': round(sum(p[2] for p in mine), 4),
            'x402_n': len(x), 'x402_payers': len(reasons), 'x402_usd': round(sum(p[2] for p in x), 4),
            'drop_self': rc['self'], 'drop_funded': rc['funded'], 'drop_same_owner': rc['same_owner'], 'drop_crawler': rc['crawler'],
            'foreign_n': len(foreign), 'foreign_payers': len(fpayers), 'foreign_clusters': len(clusters),
            'sybil_payers_collapsed': len(fpayers) - len(clusters),
            'foreign_usd': round(sum(p[2] for p in foreign), 4),
            'foreign_repeat_payers': len(repeat),
            'foreign_active_days': len(set().union(*days_by_payer.values())) if days_by_payer else 0,
            'seller_to_seller_payers': sum(1 for p in fpayers if p in sellers),
            'top_funder': top_f, 'top_funder_payers': top_n,
            'payers_funder_seen': sum(1 for p in fpayers if p in funder),
            'burst_share_1h': round(burst / len(x), 3) if x else 0,
            'cdp_claimed_calls_30d': meta['cdp_claimed_calls_30d'], 'cdp_claimed_max_unique_payers_30d': meta['cdp_claimed_max_unique_payers_30d'],
        })
    rows.sort(key=lambda r: (r['class'], -r['foreign_clusters'], -r['foreign_payers'], r['payTo']))
    with open(D / f'data/seller-metrics{OUT_SUFFIX}.csv', 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)

    # пары «продавец — чужой плательщик»: сколько платежей, денег, суток; ширина и пополнитель плательщика
    with open(D / f'data/foreign-pairs{OUT_SUFFIX}.csv', 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['seller', 'seller_class', 'payer', 'x402_tx', 'usd', 'days', 'payer_sellers_paid', 'payer_first_funder', 'sybil_collapsed'])
        for s, (_, _, foreign, fpayers) in per.items():
            agg = defaultdict(lambda: [0, 0.0, set()])
            for _, p, v, b, _ in foreign:
                a = agg[p]; a[0] += 1; a[1] += v; a[2].add(ts(b) // 86400)
            for p, (k, v, dd) in sorted(agg.items()):
                wr.writerow([s, sellers[s]['class'], p, k, round(v, 6), len(dd), len(breadth[p]), funder.get(p, ''), p in collapsed[s]])

    with open(D / f'data/payers{OUT_SUFFIX}.csv', 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['payer', 'sellers_paid_x402', 'x402_tx', 'is_catalog_seller', 'first_funder_in_window', 'first_funding_usd'])
        for p in sorted(breadth, key=lambda p: -len(breadth[p])):
            wr.writerow([p, len(breadth[p]), ptx[p], p in sellers, funder.get(p, ''), fund_amt[p] / 1e6 if p in fund_amt else ''])

    def dist(rs, key, usd=False):
        v = [r[key] for r in rs]
        if not v:
            return {'n': 0}
        bk = ([('0', 0, 0), ('(0;1)', 1e-9, 0.999999), ('[1;10)', 1, 9.999999), ('[10;100)', 10, 99.999999),
               ('[100;1000)', 100, 999.999999), ('1000+', 1000, 1e12)] if usd else
              [('0', 0, 0), ('1', 1, 1), ('2-4', 2, 4), ('5-9', 5, 9), ('10-49', 10, 49), ('50-199', 50, 199), ('200+', 200, 10**9)])
        return {
            'n': len(v), 'median': statistics.median(v), 'mean': round(statistics.mean(v), 2),
            'p25': pct(v, .25), 'p75': pct(v, .75), 'p90': pct(v, .90), 'p99': pct(v, .99), 'max': max(v),
            'share_0': round(sum(1 for x in v if x == 0) / len(v), 3),
            'buckets': {b: sum(1 for x in v if lo <= x <= hi) for b, lo, hi in bk},
        }

    def block(rs):
        return {k: dist(rs, k, usd=k.endswith('usd')) for k in
                ['x402_payers', 'foreign_payers', 'foreign_clusters', 'foreign_repeat_payers', 'foreign_usd']}

    sample = json.load(open(D / 'data/sample-small.json'))['sample']
    small = [r for r in rows if r['class'] == 'small']
    fp_all = {p for s in per for p in per[s][3]}
    summary = {
        'window': w, 'crawler_threshold_sellers': CRAWLER, 'fund_pass_used': have_fund,
        'counts': {
            'sellers': len(rows), 'by_class': Counter(r['class'] for r in rows),
            'incoming_usdc_transfers': len(pays), 'x402_eip3009_transfers': sum(1 for p in pays if p[4]),
            'x402_usd': round(sum(p[2] for p in pays if p[4]), 2),
            'x402_unique_payers': len(breadth), 'crawler_payers': sum(1 for p in breadth if len(breadth[p]) >= CRAWLER),
            'crawler_x402_tx': sum(ptx[p] for p in breadth if len(breadth[p]) >= CRAWLER),
            'crawler_x402_usd': round(sum(p[2] for p in pays if p[4] and len(breadth[p[1]]) >= CRAWLER), 2),
            'foreign_payers_unique': len(fp_all),
            'foreign_payers_with_funder_seen': sum(1 for p in fp_all if p in funder),
            'sellers_with_sybil_collapse': sum(1 for r in rows if r['sybil_payers_collapsed'] > 0),
        },
        'small_all': block(small),
        'small_with_any_x402': block([r for r in small if r['x402_n'] > 0]),
        'small_sample25': block([r for r in small if r['payTo'] in sample]),
        'small_foreign_usd_total': round(sum(r['foreign_usd'] for r in small), 2),
        'small_foreign_usd_top10_share': round(sum(sorted((r['foreign_usd'] for r in small), reverse=True)[:10]) / max(1e-9, sum(r['foreign_usd'] for r in small)), 3),
        'big': block([r for r in rows if r['class'] == 'big']),
        'platform': block([r for r in rows if r['class'] == 'platform']),
    }
    json.dump(summary, open(D / f'data/summary{OUT_SUFFIX}.json', 'w'), indent=1, default=list)
    print(json.dumps({'counts': summary['counts'], 'small_all.foreign_clusters': summary['small_all']['foreign_clusters'],
                      'small_sample25.foreign_clusters': summary['small_sample25']['foreign_clusters']}, indent=1, default=list))


if __name__ == '__main__':
    main()
