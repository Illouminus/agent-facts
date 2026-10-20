"""Собирает отчёт ../agent-demand-x402-2026-10.md из data/summary*.json и data/seller-metrics.csv.
Все числа в отчёте берутся отсюда; ручных цифр в таблицах нет.

  python3 -I make-report.py
"""
import csv, json, re
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent
OUT = D.parent / 'agent-demand-x402-2026-10.md'
S = json.load(open(D / 'data/summary.json'))
SENS = {n: json.load(open(D / f'data/summary-crawler{n}.json')) for n in (5, 10, 50, 100) if (D / f'data/summary-crawler{n}.json').exists()}
ROWS = list(csv.DictReader(open(D / 'data/seller-metrics.csv')))
for r in ROWS:
    for k, v in r.items():
        if k not in ('payTo', 'class', 'brand', 'primary_domain', 'service_names', 'description', 'top_funder'):
            for cast in (int, float):
                try:
                    r[k] = cast(v)
                    break
                except ValueError:
                    pass
SAMPLE = json.load(open(D / 'data/sample-small.json'))
CS = json.load(open(D / 'data/catalog-stats.json'))
PROBES = json.load(open(D / 'data/probes.json'))
CDP = json.load(open(D / 'data/catalog-meta.json'))
PAYAI = json.load(open(D / 'data/catalog-payai-meta.json'))
W = S['window']
C = S['counts']
small = [r for r in ROWS if r['class'] == 'small']
sample = [r for r in small if r['payTo'] in set(SAMPLE['sample'])]
FC = S['small_all']['foreign_clusters']
FC25 = S['small_sample25']['foreign_clusters']


def usd(x):
    if 0 < abs(x) < 0.001:
        return '$' + f'{x:.6f}'.rstrip('0')
    if 0 < abs(x) < 0.1:
        return f'${x:.2g}'
    return f'${x:,.2f}'.replace(',', ' ')


def n(x):
    if isinstance(x, float) and x.is_integer() and abs(x) >= 1:
        x = int(x)
    if isinstance(x, int):
        return f'{x:,}'.replace(',', ' ')
    if isinstance(x, float):
        return f'{x:.2f}'.rstrip('0').rstrip('.') if abs(x) >= 1 else f'{x:.2g}'
    return str(x)


def plural(k, one, few, many):
    k = abs(int(k))
    if k % 10 == 1 and k % 100 != 11:
        return one
    return few if 2 <= k % 10 <= 4 and not 12 <= k % 100 <= 14 else many


def short(a):
    return f'`{a[:6]}…{a[-4:]}`'


def cut(s, k=60):
    s = (s or '').replace('|', '/').strip()
    return s if len(s) <= k else s[:k - 1] + '…'


def dist_table(blocks):
    keys = ['n', 'share_0', 'p25', 'median', 'p75', 'p90', 'p99', 'max', 'mean']
    head = '| метрика | ' + ' | '.join(['продавцов', 'доля с 0', 'p25', '**медиана**', 'p75', 'p90', 'p99', 'макс', 'среднее']) + ' |'
    lines = [head, '|' + '---|' * (len(keys) + 1)]
    for title, d in blocks:
        cells = []
        for k in keys:
            v = d.get(k)
            if k == 'share_0':
                cells.append(f'{v * 100:.1f} %')
            elif k == 'median':
                cells.append(f'**{n(v)}**')
            else:
                cells.append(n(v))
        lines.append(f'| {title} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def bucket_table(d, title):
    b = d['buckets']
    return (f'| {title} | ' + ' | '.join(b) + ' |\n|' + '---|' * (len(b) + 1) + '\n| продавцов | ' +
            ' | '.join(n(v) for v in b.values()) + ' |')


def seller_table(rs, with_desc=True):
    head = ['payTo', 'домен', 'что продаёт', 'цена (медиана)', 'входящих USDC', 'плательщиков x402',
            'обходчиков', 'прочий отсев', 'чужих', '**кластеров**', 'повторных', 'чужие $', 'активных дней', 'каталог CDP: плательщиков']
    if not with_desc:
        head.remove('что продаёт')
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rs:
        price = r['price_median_usd']
        cells = [short(r['payTo']), cut(r['primary_domain'], 32)]
        if with_desc:
            cells.append(cut(r['service_names'] or r['description'], 55))
        cells += [usd(price) if price != '' else '—', n(r['all_in_n']), n(r['x402_payers']), n(r['drop_crawler']),
                  n(r['drop_self'] + r['drop_funded'] + r['drop_same_owner']), n(r['foreign_payers']),
                  f"**{n(r['foreign_clusters'])}**", n(r['foreign_repeat_payers']), usd(r['foreign_usd']),
                  n(r['foreign_active_days']), n(r['cdp_claimed_max_unique_payers_30d'])]
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def brands():
    agg = defaultdict(lambda: defaultdict(float))
    for r in ROWS:
        if r['class'] != 'big':
            continue
        a = agg[r['brand']]
        a['addrs'] += 1
        for k in ('all_in_n', 'x402_n', 'x402_payers', 'drop_crawler', 'foreign_payers', 'foreign_clusters', 'foreign_repeat_payers', 'foreign_usd'):
            a[k] += r[k]
        # метрика каталога у адресов одного бренда часто относится к одним и тем же ресурсам — берём максимум, не сумму
        a['cdp_claimed_max_unique_payers_30d'] = max(a['cdp_claimed_max_unique_payers_30d'], r['cdp_claimed_max_unique_payers_30d'])
    return sorted(agg.items(), key=lambda kv: -kv[1]['foreign_clusters'])


def brand_table(items):
    head = ['бренд', 'адресов payTo', 'плательщиков x402*', 'обходчиков*', 'чужих*', '**кластеров***', 'повторных*', 'чужие $', 'каталог CDP: плательщиков (макс. по ресурсу)']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for b, a in items:
        lines.append(f"| {b} | {int(a['addrs'])} | {n(int(a['x402_payers']))} | {n(int(a['drop_crawler']))} | {n(int(a['foreign_payers']))} | "
                     f"**{n(int(a['foreign_clusters']))}** | {n(int(a['foreign_repeat_payers']))} | {usd(a['foreign_usd'])} | {n(int(a['cdp_claimed_max_unique_payers_30d']))} |")
    return '\n'.join(lines)


def sens_table():
    lines = ['| порог «обходчика» (платил ≥ N продавцам) | обходчиков-кошельков | медиана кластеров у мелких | p75 | p90 | доля мелких с 0 |',
             '|---|---|---|---|---|---|']
    allS = dict(SENS); allS[S['crawler_threshold_sellers']] = S
    for k in sorted(allS):
        s = allS[k]; d = s['small_all']['foreign_clusters']
        mark = ' (основной)' if k == S['crawler_threshold_sellers'] else ''
        lines.append(f"| {k}{mark} | {n(s['counts']['crawler_payers'])} | **{n(d['median'])}** | {n(d['p75'])} | {n(d['p90'])} | {d['share_0'] * 100:.1f} % |")
    lines.append(f"| без фильтра обходчиков (сырые плательщики x402) | — | **{n(S['small_all']['x402_payers']['median'])}** | {n(S['small_all']['x402_payers']['p75'])} | {n(S['small_all']['x402_payers']['p90'])} | {S['small_all']['x402_payers']['share_0'] * 100:.1f} % |")
    return '\n'.join(lines)


top_small = sorted(small, key=lambda r: (-r['foreign_clusters'], -r['foreign_payers']))[:15]
big_items = brands()
CONTRAST = [b for b in ('CoinGecko', 'Nansen', 'Glassnode', 'Exa', 'Bitrefill', 'Pocket Network', 'Apify') if b in dict(big_items)]
big_contrast = [(b, dict(big_items)[b]) for b in CONTRAST]
plat = sorted([r for r in ROWS if r['class'] == 'platform'], key=lambda r: -r['foreign_clusters'])
n_sm_10 = sum(1 for r in small if r['foreign_clusters'] >= 10)
n_sm_rep5 = sum(1 for r in small if r['foreign_repeat_payers'] >= 5)
n_sm_usd100 = sum(1 for r in small if r['foreign_usd'] >= 100)
top10_usd = sorted(small, key=lambda r: -r['foreign_usd'])[:10]

# помощники для текста выводов
BY_DOMAIN = defaultdict(list)
for r in ROWS:
    BY_DOMAIN[r['primary_domain']].append(r)
def seller(domain):  # самый активный адрес продавца с этим доменом
    return max(BY_DOMAIN[domain], key=lambda r: r['foreign_payers'])
def kind(probe):  # 23 байта кода = указатель делегирования EIP-7702 (0xef0100 + адрес), то есть это EOA
    return 'EOA' if probe['codeBytes'] == 0 else 'EOA с делегированием EIP-7702' if probe['codeBytes'] == 23 else f"контракт, {probe['codeBytes']} байт кода"
def funder_probe(domain):
    return next(f for f in PROBES['funders'] if f['domain'] == domain)
PAIRS = list(csv.DictReader(open(D / 'data/foreign-pairs.csv')))
def farm(prefix):  # сколько кошельков пополнил адрес и скольким продавцам они платили
    ps = {r['payer'] for r in PAIRS if r['payer_first_funder'].startswith(prefix)}
    ss = {r['seller'] for r in PAIRS if r['payer'] in ps}
    br = sorted(int(r['payer_sellers_paid']) for r in PAIRS if r['payer'] in ps)
    return {'wallets': len(ps), 'sellers': len(ss), 'breadth_min': br[0] if br else 0, 'breadth_max': br[-1] if br else 0}
BRAND_LINE = '; '.join(f"{b} — {n(int(a['foreign_clusters']))} кластеров, {n(int(a['foreign_repeat_payers']))} повторных, {usd(a['foreign_usd'])}" for b, a in big_contrast)
TEXT = Path(D / 'report-text.md').read_text() if (D / 'report-text.md').exists() else ''
CRAWLER_EXAMPLES = 'Например, ' + '; '.join(
    f"`{c['address'][:6]}…{c['address'][-4:]}` заплатил {n(c['sellers_paid_x402'])} продавцам ({n(c['x402_tx'])} {plural(c['x402_tx'], 'платёж', 'платежа', 'платежей')}), nonce {c['nonce']}, код {c['codeBytes']} байт"
    for c in PROBES['crawlers'][:3]) + '. Nonce 0 значит, что кошелёк сам не отправил ни одной транзакции: он только подписывает платежи, а газ платит фасилитатор (`data/probes.json`).'
ctx = dict(kind=kind, plural=plural, seller=seller, funder_probe=funder_probe, farm=farm, BRAND_LINE=BRAND_LINE, round=round, len=len, sum=sum, sorted=sorted, CS=CS, PROBES=PROBES, CRAWLER_EXAMPLES=CRAWLER_EXAMPLES, N_CDP_BASE=CS['cdp']['base_payTo'], N_PAYAI_BASE=CS['payai']['base_payTo'],
           N_PAYAI_ONLY=CS['payai_only_base_payTo'], top_small=top_small, big_contrast=big_contrast, small=small, ROWS=ROWS, SENS=SENS, sample=sample, S=S, C=C, W=W, FC=FC, FC25=FC25, n=n, usd=usd, n_small=len(small), n_sm_10=n_sm_10, n_sm_rep5=n_sm_rep5,
           n_sm_usd100=n_sm_usd100, CDP=CDP, PAYAI=PAYAI)

md = f"""Мелкий независимый продавец в x402 получает в медиане **{n(FC['median'])}** {plural(FC['median'], 'уникального чужого плательщика', 'уникальных чужих плательщиков', 'уникальных чужих плательщиков')} за 30 дней (выборка {n(FC['n'])} продавцов: вся совокупность мелких продавцов на Base из двух открытых каталогов; в случайной подвыборке из {FC25['n']} медиана {n(FC25['median'])}; при строгом фильтре обходчиков (≥ 5 продавцов) — {n(SENS[5]['small_all']['foreign_clusters']['median'])}; повторных чужих плательщиков в медиане {n(S['small_all']['foreign_repeat_payers']['median'])}, чужих денег — {usd(S['small_all']['foreign_usd']['median'])}).

# Спрос автономных агентов на платные эндпоинты x402: замер по блокчейну Base, октябрь 2026

Окно: блоки {n(W['fromBlock'])}–{n(W['toBlock'])} сети Base = {W['fromTime']} → {W['toTime']} (30 суток, [`x402-demand/data/window.json`](x402-demand/data/window.json)).
Все числа ниже посчитаны скриптами из [`x402-demand/`](x402-demand/) по сырым логам Base; источник каждой цифры — [`data/summary.json`](x402-demand/data/summary.json) и [`data/seller-metrics.csv`](x402-demand/data/seller-metrics.csv), если не указано иное.

{TEXT.split('<!-- SPLIT -->')[0] if TEXT else ''}

## 3. Распределение по всей совокупности мелких продавцов

«Плательщики x402» — уникальные адреса, заплатившие продавцу USDC через EIP-3009 в окне. «Чужие» — после отсева самоплатежей, пополненных продавцом, кошельков того же владельца и обходчиков (платил ≥ {S['crawler_threshold_sellers']} продавцам). «Кластеры» — чужие со схлопнутыми сибилами (общий раздающий пополнитель). «Повторные» — чужие, платившие в ≥ 2 разных суток.

{dist_table([
    ('плательщиков x402 (сырые)', S['small_all']['x402_payers']),
    ('чужих плательщиков', S['small_all']['foreign_payers']),
    ('**чужих кластеров** (основная)', S['small_all']['foreign_clusters']),
    ('повторных чужих', S['small_all']['foreign_repeat_payers']),
    ('чужие поступления, $', S['small_all']['foreign_usd']),
])}

{bucket_table(S['small_all']['foreign_clusters'], 'чужих кластеров за 30 дней')}

{bucket_table(S['small_all']['foreign_usd'], 'чужие поступления за 30 дней, $')}

Только среди мелких, у кого в окне был хотя бы один платёж x402 (n = {n(S['small_with_any_x402']['foreign_clusters']['n'])}): медиана чужих кластеров **{n(S['small_with_any_x402']['foreign_clusters']['median'])}**, p75 {n(S['small_with_any_x402']['foreign_clusters']['p75'])}, p90 {n(S['small_with_any_x402']['foreign_clusters']['p90'])}; медиана сырых плательщиков x402 {n(S['small_with_any_x402']['x402_payers']['median'])}.

Деньги: все мелкие вместе получили от чужих плательщиков {usd(S['small_foreign_usd_total'])} за 30 дней; доля десяти крупнейших получателей — {S['small_foreign_usd_top10_share'] * 100:.1f} %. Мелких с ≥ 10 чужими кластерами — {n(n_sm_10)} из {n(len(small))}; с ≥ 5 повторными чужими плательщиками — {n_sm_rep5}; с чужими поступлениями ≥ $100 — {n_sm_usd100}.

## 4. Случайная выборка {len(sample)} мелких продавцов (seed {SAMPLE['seed']}, [`data/sample-small.json`](x402-demand/data/sample-small.json))

{dist_table([
    ('плательщиков x402 (сырые)', S['small_sample25']['x402_payers']),
    ('**чужих кластеров**', S['small_sample25']['foreign_clusters']),
    ('повторных чужих', S['small_sample25']['foreign_repeat_payers']),
    ('чужие поступления, $', S['small_sample25']['foreign_usd']),
])}

{seller_table(sorted(sample, key=lambda r: (-r['foreign_clusters'], -r['x402_payers'])))}

Полные адреса, описание и все столбцы — в [`data/seller-metrics.csv`](x402-demand/data/seller-metrics.csv) (фильтр по payTo из `sample-small.json`). «Каталог CDP: плательщиков» — собственная метрика каталога `quality.l30DaysUniquePayers` (максимум по ресурсам продавца), приведена для сверки, не для выводов.

## 5. Потолок: 15 мелких продавцов с наибольшим числом чужих кластеров

{seller_table(top_small)}

## 6. Контраст: крупные бренды и платформы

\\* суммы по всем адресам payTo бренда; один плательщик, плативший двум адресам бренда, посчитан дважды.

{brand_table(big_contrast)}

Все {len(big_items)} брендов из каталога: {', '.join(f"{b} ({n(int(a['foreign_clusters']))})" for b, a in big_items)} — в скобках чужие кластеры.

Платформы-перепродавцы (семейство stable*.dev Merit Systems, Locus, Sponge, PayAI): {len(plat)} адресов, медиана чужих кластеров **{n(S['platform']['foreign_clusters']['median'])}**, максимум {n(S['platform']['foreign_clusters']['max'])}; крупные бренды: медиана **{n(S['big']['foreign_clusters']['median'])}**, максимум {n(S['big']['foreign_clusters']['max'])} (по адресам, n = {S['big']['foreign_clusters']['n']}).

## 7. Шум: сколько отсеяно и насколько вывод зависит от порогов

Во всём окне по {n(C['sellers'])} адресам продавцов: {n(C['incoming_usdc_transfers'])} {plural(C['incoming_usdc_transfers'], 'входящий перевод', 'входящих перевода', 'входящих переводов')} USDC, из них {n(C['x402_eip3009_transfers'])} через EIP-3009 на {usd(C['x402_usd'])}; уникальных плательщиков x402 — {n(C['x402_unique_payers'])}. Обходчиков (платили ≥ {S['crawler_threshold_sellers']} продавцам) — {n(C['crawler_payers'])} {plural(C['crawler_payers'], 'кошелёк', 'кошелька', 'кошельков')}; на них приходится {n(C['crawler_x402_tx'])} платежей x402 на {usd(C['crawler_x402_usd'])}. Продавцов, у которых сработало схлопывание сибилов, — {n(C['sellers_with_sybil_collapse'])}. Пополнитель в окне найден для {n(C['foreign_payers_with_funder_seen'])} из {n(C['foreign_payers_unique'])} чужих плательщиков. В строках с порогом 50 и 100 кошельки шириной 20–49 и 20–99 продавцов считаются чужими, но их пополнения не скачивались, поэтому сибилы среди них не склеиваются.

{sens_table()}

{TEXT.split('<!-- SPLIT -->')[1] if TEXT and '<!-- SPLIT -->' in TEXT else ''}
"""
# в тексте отчёта числа подставляются из данных: {{выражение}}
md = re.sub(r'\{\{(.+?)\}\}', lambda m: str(eval(m.group(1), ctx)), md)
OUT.write_text(md)
print('wrote', OUT, len(md), 'chars')
