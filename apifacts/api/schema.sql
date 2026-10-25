-- observations.sqlite (never in git). Transient state only: losing it loses nothing verified.
-- Columns of `observations` = schema/observation.schema.json, in order (tested). No bodies,
-- headers, query strings or raw IPs: reporter_net is sha256(weekly salt ‖ IPv4 /16 or IPv6 /32).

CREATE TABLE IF NOT EXISTS observations (
    id                INTEGER PRIMARY KEY,
    received_at       TEXT    NOT NULL,
    service           TEXT    NOT NULL,
    method            TEXT    NOT NULL,
    path_template     TEXT    NOT NULL,
    status            INTEGER,
    error_hash        TEXT,
    normalized_error  TEXT,
    reporter_net      TEXT    NOT NULL,
    reporter_ua_class TEXT    NOT NULL,
    sdk_package       TEXT,
    sdk_version       TEXT,
    env_guess         TEXT,
    vantage_country   TEXT
);

-- quorum grouping (spec 05) and the per-network daily cap
CREATE INDEX IF NOT EXISTS observations_group
    ON observations (service, method, path_template, error_hash);
CREATE INDEX IF NOT EXISTS observations_net
    ON observations (reporter_net, received_at);

-- one salt per period (Monday 00:00 UTC → next Monday); `day` is the period's Monday, and
-- older rows are deleted when a new period starts
CREATE TABLE IF NOT EXISTS salts (
    day  TEXT PRIMARY KEY,
    salt BLOB NOT NULL
);

-- anonymous daily metrics: stored, dropped_*, unregistered_target and unregistered_target:<host>,
-- where <host> is a seed candidate's API host or `other` (no other identifiers of any kind)
CREATE TABLE IF NOT EXISTS counters (
    day  TEXT    NOT NULL,
    name TEXT    NOT NULL,
    n    INTEGER NOT NULL,
    PRIMARY KEY (day, name)
);
