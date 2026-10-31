# `The version you specified in the "X-GitHub-API-Version" request header, "2021-01-01", is not a supported version. The following versions are currently supported: "2026-03-10" (most recent) and "2022-11-28".`

**GitHub REST API · GET /repos/{owner}/{repo} · HTTP 400**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-30 · 55 confirmations from 2 vantages

> An X-GitHub-Api-Version that is not a supported version, such as 2021-01-01, returns HTTP 400 Bad Request whose errors field is a string naming the supported versions.

## What to do

1. Send header X-GitHub-Api-Version = 2026-03-10.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:github:probe:repo-api-version-unsupported` (declarative, [source](../../probes/github/repo-api-version-unsupported.yaml)) · official doc: <https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#not-a-supported-version>

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `the version you specified in the "x-github-api-version" request header, "####-##-##", is not a supported version. the following versions are currently supported: "####-##-##" (most recent) and "####-##-##".`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"GET","url":"https://api.github.com/repos/{owner}/{repo}"},"error":{"status":400,"body_excerpt":"the version you specified in the \"x-github-api-version\" request header, \"####-##-##\", is not a supported version. the following versions are currently supported: \"####-##-##\" (most recent) and \"####-##-##\"."}}'
```

YAML: [facts/github/unsupported-api-version-400.yaml](../../facts/github/unsupported-api-version-400.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
