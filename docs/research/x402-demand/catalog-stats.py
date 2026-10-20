"""Статистика каталогов по сырым страницам: сети, способы перевода, схемы, активы на Base.

  python3 -I catalog-stats.py -> data/catalog-stats.json
"""
import glob, gzip, json
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parent
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
BASE = {'eip155:8453', 'base'}


def main():
    out = {}
    base_addrs = {}
    for name, d in [('cdp', 'raw/catalog'), ('payai', 'raw/catalog-payai')]:
        nets, methods, schemes, assets = Counter(), Counter(), Counter(), Counter()
        res, addrs, offers = set(), set(), 0
        for f in sorted(glob.glob(str(D / d / '*.json.gz'))):
            for it in json.loads(gzip.open(f).read())['items']:
                if it['resource'] in res:
                    continue
                res.add(it['resource'])
                for a in it.get('accepts', []):
                    nets[a.get('network')] += 1
                    if a.get('network') not in BASE:
                        continue
                    offers += 1
                    methods[(a.get('extra') or {}).get('assetTransferMethod', 'default(eip3009)')] += 1
                    schemes[a.get('scheme')] += 1
                    assets['USDC' if str(a.get('asset', '')).lower() == USDC else 'other'] += 1
                    pt = str(a.get('payTo') or '')
                    if pt.startswith('0x') and len(pt) == 42:
                        addrs.add(pt.lower())
        base_addrs[name] = addrs
        out[name] = {'resources': len(res), 'base_offers': offers, 'base_payTo': len(addrs),
                     'networks_top': nets.most_common(12), 'base_transfer_method': methods.most_common(),
                     'base_scheme': schemes.most_common(), 'base_asset': assets.most_common()}
    out['payai_only_base_payTo'] = len(base_addrs['payai'] - base_addrs['cdp'])
    out['overlap_base_payTo'] = len(base_addrs['payai'] & base_addrs['cdp'])
    out['union_base_payTo'] = len(base_addrs['payai'] | base_addrs['cdp'])
    tot = Counter()
    for name in ('cdp', 'payai'):
        for k in ('base_transfer_method', 'base_scheme', 'base_asset'):
            for key, v in out[name][k]:
                tot[(k, key)] += v
        tot[('base_offers', '')] += out[name]['base_offers']
    out['both_base'] = {f'{k}:{key}' if key else k: v for (k, key), v in sorted(tot.items())}
    json.dump(out, open(D / 'data/catalog-stats.json', 'w'), indent=1)
    print(json.dumps(out['both_base'], indent=1), out['union_base_payTo'], out['payai_only_base_payTo'])


if __name__ == '__main__':
    main()
