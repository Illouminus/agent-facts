"""Assemble docs/research/seed-100-2026-10-20.md from data/ranked.json + data/wave1.json (run after rank.py)."""
import json, collections, datetime
from pathlib import Path
D = Path(__file__).parent / "data"
R = json.loads((D / "ranked.json").read_text())
W1 = json.loads((D / "wave1.json").read_text())
MCP = json.loads((D / "mcp-servers.json").read_text()) if (D / "mcp-servers.json").exists() else {"servers": [], "pages": 0}
OUT = Path(__file__).parent.parent / "seed-100-2026-10-20.md"
by = {x["service"]: x for x in R}
n = lambda v: f"{v:,}".replace(",", " ")
today = datetime.date.today().isoformat()

def row(x):
    return (f"| {x['rank']} | {x['service']} | {x['category']} | {x['probe_class']} | {x['score']:.3f} | {n(x['downloads_month'])} "
            f"| {n(x['stars'])} | {n(x['so_count'])} | {x['mcp_servers']} |")

hdr = ("| # | service | category | probe | score | downloads/mo | stars | SO tag | MCP |\n"
       "|---|---------|----------|-------|-------|--------------|-------|--------|-----|")
top100 = R[:100]
cats = collections.Counter(x["category"] for x in top100)
probe = collections.Counter(x["probe_class"] for x in top100)
excluded = [x for x in R if x["tos"] == "prohibited"]
restricted = [x for x in top100 if x["tos"] == "restricted"]
bad = [(x["service"], k.split("_")[0], x[k]) for x in R for k in ("pypi_status", "npm_status", "gh_status", "so_status")
       if x[k] not in (None, 200) and x.get(k.split("_")[0])]
measured = sum(1 for x in R if x["measured"])

wave_rows = []
for s in W1:
    x = by[s]
    need = {"keyless": "ничего (публичные GET без ключа)", "sandbox": "аккаунт + sandbox/test-ключ через keyput",
            "key_free": "бесплатный ключ через keyput"}[x["probe_class"]]
    wave_rows.append(f"| {x['rank']} | **{s}** | {x['category']} | {x['probe_class']} | {x['score']:.3f} | {need} |")

md = f"""# Семя реестра: 100 ресурсов по замеренным сигналам (2026-10-20)

Готово когда: ранжированный список 100 сервисов с воспроизводимым счётом, волна 1 из 10 плотных сервисов
для старта, список исключённых по ToS и список непроверенных догадок. Утверждает Edouard (волна 1 — тап).

## Зачем и как читать

Реестру нужно семя: сервисы, о которых агенты чаще всего спрашивают после отказа, где у нас есть
законный и дешёвый путь к пробе и где фактов хватит на ≥ 10 на сервис (решение 18.10: плотно, не
тонко). «100» — вселенная для всех волн; волна 1 — верхние 10 с ограничениями ниже; дальше волны по
таблице сверху вниз, по мере ключей Edouard и свободных агент-часов.

## Метод (всё воспроизводимо, без LLM в счёте)

1. **Вселенная**: {len(R)} кандидатов, составлена вручную агентом из знания рынка по категориям (LLM,
   поиск/скрейпинг, платежи, почта, мессенджеры, devtools/облака, БД, auth, CRM/поддержка/продуктивность,
   аналитика, карты, финансы/крипта, госданные, наука, соцсети, коммерция, безопасность).
   Файл: `seed-100/candidates.py`. Gemini (agy) просили о той же вселенной — вернул пересказ вместо JSON
   (ушёл «проверять пакеты»); второй запрос дал 97 ловушек по 60 сервисам как **непроверенные подсказки**
   для W7: `seed-100/data/gotchas-gemini-unverified.json`.
2. **Сигналы** (замер {today}, скрипт `seed-100/measure.py`, {measured} из {len(R)} строк замерены):

| Сигнал | Что меряет | Источник |
|--------|------------|----------|
| downloads/mo | использование SDK: max(PyPI за месяц, npm за месяц) | pypistats.org/api, api.npmjs.org |
| stars | зрелость/внимание к официальному SDK или серверу | GitHub REST через gh |
| SO tag | накопленная боль: число вопросов с тегом на Stack Overflow | api.stackexchange.com (без ключа, квота 300/день) |
| MCP | притяжение для агентов: серверов в официальном реестре MCP, чьё имя/описание упоминает сервис | registry.modelcontextprotocol.io, скачан целиком ({n(len(MCP['servers']))} серверов, {MCP['pages']} страниц), подсчёт локально по границе слова |

3. **Счёт**: каждый сигнал → log1p → min-max по вселенной → взвешенная сумма
   0.45·downloads + 0.15·stars + 0.25·SO + 0.15·MCP; затем множители осуществимости:
   probe_class keyless/sandbox ×1.0, key_free ×0.95, local ×0.85, trial ×0.8, paid ×0.7;
   ToS ok ×1.0, restricted ×0.8, prohibited → исключён. Скрипт `seed-100/rank.py`, веса в его шапке.
4. **Волна 1**: верхние по счёту среди probe_class ∈ {{keyless, sandbox, key_free}} и ToS ok, не больше
   2 на категорию, не меньше 3 без ключа (чтобы W7 стартовал до единого тапа).

### Оговорки, которые надо помнить

- Загрузки SDK завышены транзитивными зависимостями (boto3, google-api-python-client, openai тянут
  фреймворки); это сознательно принято как прокси «сколько кода трогает этот интерфейс».
- Тег SO выбран вручную; у части сервисов тега нет или он узкий (`None`/0 = неизвестно, не «нет боли»).
- MCP-подсчёт по подстроке шумит на коротких и общих именах (box, square, render, linear); вес 0.15.
- Сервисы «local» (библиотеки, самохост) меряются, но пробуются только клиентской песочницей (W9), в
  волну 1 не входят.
- Это сигналы выбора семени, не факты реестра. Любое число ниже — только по этому замеру и дате.

## Волна 1 (10 сервисов, ≥ 10 фактов каждый) — на утверждение

| # | service | category | probe | score | что нужно от Edouard |
|---|---------|----------|-------|-------|----------------------|
{chr(10).join(wave_rows)}

Правила отбора дали ограничение «≤ 2 на категорию»; если Edouard хочет заменить сервис — взять следующий
по таблице ниже в той же категории.

## 100 ресурсов по счёту

Категорий в сотне: {', '.join(f'{k} {v}' for k, v in cats.most_common())}.
Класс пробы в сотне: {', '.join(f'{k} {v}' for k, v in probe.most_common())}.

{hdr}
{chr(10).join(row(x) for x in top100)}

## Исключены по ToS (автоматический доступ или публикация замеров запрещены)

{chr(10).join(f'- {x["service"]} ({x["vendor"]}): score без штрафа {x["score_raw"]:.3f}' for x in excluded) or '- нет'}

В сотне с пометкой restricted (политика использования или серая зона скрейпинга; пробы только по их
правилам, ≤ 1 запрос/с и честный User-Agent): {', '.join(x['service'] for x in restricted) or 'нет'}.

## Догадки, которые замер не подтвердил (имя пакета/репо/тега дало не-200)

{chr(10).join(f'- {s}: {k} → {st}' for s, k, st in bad) or '- все обращения вернули 200'}

Для этих строк соответствующий сигнал считается 0; имя надо поправить в `candidates.py` и перезапустить
`measure.py` (докачивает только недостающее).

## Кандидаты 101–{len(R)}

{', '.join(x['service'] for x in R[100:])}

## Файлы

`seed-100/candidates.py` (вселенная), `measure.py` (замер, возобновляемый), `mcp-index.py` (реестр MCP
целиком → `data/mcp-servers.json`), `rank.py` (счёт, волна 1), `report.py` (этот документ),
`data/measurements.json`, `data/ranked.csv|json`, `data/wave1.json`, `data/gotchas-gemini-unverified.json`.
"""
OUT.write_text(md)
print("wrote", OUT, len(md), "chars")
