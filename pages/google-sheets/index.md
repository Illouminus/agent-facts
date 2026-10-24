# Google Sheets API

Hosts: `sheets.googleapis.com` · 20 facts

## Error meanings

- ✅ verified:server:prod · [`unable to parse range: agentfactsnosuchsheet!a#`](batch-get-fails-whole.md) · GET /v4/spreadsheets/{spreadsheet_id}/values:batchGet · env prod
- ✅ verified:server:prod · [`unable to parse range: sheet#!a#`](default-sheet-name-follows-locale.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [`request contains an invalid argument.`](invalid-fields-mask-generic-400.md) · GET /v4/spreadsheets/{spreadsheet_id} · env prod
- ✅ verified:server:prod · [`invalid value at 'value_render_option' (type.googleapis.com/google.apps.sheets.v#.valuerenderoption), "pretty"`](invalid-value-render-option-400.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [`requested entity was not found.`](spreadsheet-not-found-404.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [`unable to parse range: agentfactsnosuchsheet!a#`](unknown-sheet-unable-to-parse.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod

## Rate limits

- 🔵 official · [Read and write requests are each limited to 300 per minute per project and 60 per minute per user per project, refilled every minute; going over returns HTTP 429.](quota-per-project-and-user.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod

## Silent behavior

- ✅ verified:server:prod · [With majorDimension=COLUMNS an empty cell before a column's last value comes back as "" and the empty cells after it are dropped.](columns-major-inner-empty-cells.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [UNFORMATTED_VALUE with dateTimeRenderOption=FORMATTED_STRING returns dates as locale-formatted strings ("24/10/2026") while numbers stay JSON numbers.](date-time-formatted-string.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [values.get on a range with no data returns HTTP 200 with range and majorDimension but no values field at all, not values: \[\].](empty-range-omits-values.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [By default values.get returns every cell as a string formatted in the spreadsheet's locale: on a fr_FR file 3.14159 comes back as "3,14159", a date as "24/10/2026" and a boolean as "TRUE".](formatted-values-follow-locale.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [With valueRenderOption=FORMULA formulas come back as text in the spreadsheet locale's syntax: =DATE(2026;10;24) with semicolons on a fr_FR file, while plain numbers and booleans stay typed.](formulas-in-locale-syntax.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [The untouched first sheet of a new spreadsheet has a grid of 1000 rows by 26 columns (gridProperties.rowCount and columnCount), the bounds ranges are clipped to.](new-sheet-grid-1000x26.md) · GET /v4/spreadsheets/{spreadsheet_id} · env prod
- ✅ verified:server:prod · [A range that runs past the sheet's grid is clipped instead of refused: A1:ZZZ1 comes back as A1:Z1 and A1:B2000 as A1:B1000 on a 1000x26 sheet, with HTTP 200.](range-clipped-to-grid.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [With valueRenderOption=UNFORMATTED_VALUE numbers and booleans are JSON numbers and booleans, and a date is its serial number: 2026-10-24 comes back as 46319.](unformatted-dates-are-serial-numbers.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [values is a ragged array: each row ends at its last non-empty cell (a two-cell row of A1:E5 has two items) and an empty row between filled ones comes back as \[\].](value-rows-not-padded.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [An open range such as A:A is answered with explicit bounds, A1:A1000 on a 1000-row sheet, and the first sheet's quoted name ('Feuille 1'!A1:A1000).](whole-column-range-expanded.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod

## Auth quirks

- ✅ verified:server:prod · [`api key not valid. please pass a valid api key.`](invalid-api-key-400.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod
- ✅ verified:server:prod · [`method doesn't allow unregistered callers (callers without established identity). please use api key or other form of api consumer identity to call this api.`](missing-api-key-403.md) · GET /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod

## Latency profiles

- 🔵 official · [A request that Sheets processes for more than 180 seconds returns a timeout error; a 2 MB payload is the recommended maximum.](request-timeout-180s.md) · PUT /v4/spreadsheets/{spreadsheet_id}/values/{range} · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
