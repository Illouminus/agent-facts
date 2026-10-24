# agent-facts registry

Facts about how APIs, SDKs and CLIs behave, for AI agents; each page shows how its fact was established. Registry version 2026-10-24 · 5 services · 96 facts.

| Service | Facts | ✅ verified | 🔵 official | 🟡 reported | ⚪ stale | ⛔ retracted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [GitHub REST API](github/index.md) | 23 | 16 | 7 | 0 | 0 | 0 |
| [Gemini API](google-gemini/index.md) | 17 | 13 | 4 | 0 | 0 | 0 |
| [PyPI (Python Package Index)](pypi/index.md) | 16 | 12 | 4 | 0 | 0 | 0 |
| [Solana JSON-RPC (public mainnet endpoint)](solana/index.md) | 14 | 11 | 3 | 0 | 0 | 0 |
| [Stripe API](stripe/index.md) | 26 | 23 | 3 | 0 | 0 | 0 |

## Machine access

`POST https://facts.baillot.dev/v0/check` with the failing request's method, URL and error returns the matching facts and their typed fixes. Every fact page is titled with its normalized error string.

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
