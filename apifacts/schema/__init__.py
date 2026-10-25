"""JSON Schemas of the registry (`schema/*.schema.json`) and validators built from them."""

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_NAMES = ("fact", "fix", "observation", "probe", "service")

_PACKAGED = Path(__file__).with_name("json")  # wheel: force-included copy of schema/
_REPO = Path(__file__).resolve().parents[2] / "schema"  # source checkout / editable install


def schema_dir() -> Path:
    return _PACKAGED if _PACKAGED.is_dir() else _REPO


@cache
def load_schema(name: str) -> dict:
    if name not in SCHEMA_NAMES:
        raise KeyError(f"unknown schema {name!r}; expected one of {SCHEMA_NAMES}")
    return json.loads((schema_dir() / f"{name}.schema.json").read_text(encoding="utf-8"))


@cache
def schema_registry() -> Registry:
    schemas = [
        load_schema(n) for n in SCHEMA_NAMES if (schema_dir() / f"{n}.schema.json").is_file()
    ]
    return Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)


@cache
def validator_for(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=schema_registry())
