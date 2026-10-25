# 02 · Fix vocabulary v0.1

**Done when:** `schema/fix.schema.json` encodes exactly this table as a discriminated union on `action`,
every `fixes[]` entry in `facts/` validates, and `apifacts render-fix` turns any entry into one
English sentence from a template (tested per action).

Fixes are **data, not advice**: closed enumeration, typed parameters, rendered to prose by us. Agents can
apply them mechanically; nothing in a fix can carry a URL outside the vendor's registered hosts, a shell
command, or free text.

| `action` | Parameters | Rendered as |
|----------|------------|-------------|
| `retry_after_header` | `header` (default `Retry-After`), `unit` (`s`\|`ms`), `max_attempts` | Wait the number of {unit} in {header}, then retry (≤ {max_attempts}) |
| `backoff_exponential` | `base_ms`, `factor`, `max_ms`, `max_attempts`, `jitter` (bool) | Retry with exponential backoff from {base_ms} ms × {factor}, cap {max_ms} ms |
| `set_header` | `name`, `value_source` (`literal:<v>`\|`new_uuid_per_request`\|`new_uuid_per_distinct_request`\|`account_setting:<key>`) | Send header {name} = {value_source} |
| `set_param` | `name`, `value_source` (as above or `literal:<v>`), `location` (`query`\|`body`\|`header`) | Set {location} parameter {name} to {value_source} |
| `remove_param` | `name`, `location` | Omit {location} parameter {name} |
| `use_endpoint` | `method`, `path_template` (must be a registered template) | Call {method} {path_template} instead |
| `paginate_with` | `cursor_field`, `param_name`, `page_size_max` | Paginate by {cursor_field} via {param_name}, ≤ {page_size_max} per page |
| `pin_sdk_version` | `package`, `ecosystem`, `constraint` | Pin {package} to {constraint} |
| `upgrade_sdk` | `package`, `ecosystem`, `min_version` | Upgrade {package} to ≥ {min_version} |
| `switch_env` | `to` (`prod`\|`sandbox`), `reason_kind` (`feature_missing`\|`state_unreachable`) | Use the {to} environment: {reason_kind} |
| `request_scope` | `scope` | Request OAuth scope {scope} |
| `wait_for_state` | `account_state`, `typical_delay_s` | Wait until account state {account_state} (typically {typical_delay_s} s) |
| `enable_in_dashboard` | `setting_key`, `vendor_doc_url` (vendor host only) | A human must enable {setting_key} in the vendor dashboard |
| `reduce_payload` | `field`, `max_bytes`\|`max_items` | Keep {field} ≤ {max} |
| `encode_as` | `field`, `encoding` (`base64`\|`url`\|`json_string`\|`rfc3339`) | Encode {field} as {encoding} |
| `none_known` | `reason_kind` (`vendor_side`\|`investigating`\|`by_design`) | No client-side fix known ({reason_kind}) |

Rules: every fact has ≥ 1 fix (`none_known` counts); max 3 fixes per fact; `vendor_doc_url` and
`path_template` are validated against the service registration; rendering templates live in
`apifacts/fixes/templates.py` and have one test per action with a golden sentence.
