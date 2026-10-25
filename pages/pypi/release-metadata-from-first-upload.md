# JSON API metadata comes from the values given at upload time, not from the files, and the first upload of a release is stored: later uploads to that release do not update it.

**PyPI (Python Package Index) · GET /pypi/{project}/{version}/json**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://docs.pypi.org/api/json/#get-a-project>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://pypi.org/pypi/{project}/{version}/json"}}'
```

YAML: [facts/pypi/release-metadata-from-first-upload.yaml](../../facts/pypi/release-metadata-from-first-upload.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
