"""Contract-test harness: validate live API responses against the OpenAPI component schemas (T014).

Loads ``specs/001-azure-pricing-dashboard/contracts/pricing-api.openapi.yaml`` and exposes a
``validate_schema(name, payload)`` fixture that resolves ``$ref`` against the document's
``components/schemas`` section using jsonschema.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPENAPI_PATH = (
    _REPO_ROOT / "specs" / "001-azure-pricing-dashboard" / "contracts" / "pricing-api.openapi.yaml"
)


@pytest.fixture(scope="session")
def openapi_doc() -> dict:
    return yaml.safe_load(_OPENAPI_PATH.read_text(encoding="utf-8"))


def _normalize_nullable(node):
    """Translate OAS 3.0 ``nullable: true`` into JSON-Schema ``type: [<t>, 'null']`` (recursively).

    jsonschema validators ignore the ``nullable`` keyword, so without this a nullable ``number``
    field would reject ``null``. This keeps the published contract intact while letting the harness
    interpret it correctly.
    """
    if isinstance(node, dict):
        if node.get("nullable") is True and isinstance(node.get("type"), str):
            node["type"] = [node["type"], "null"]
            node.pop("nullable", None)
        for value in node.values():
            _normalize_nullable(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_nullable(item)
    return node


@pytest.fixture(scope="session")
def validate_schema(openapi_doc):
    doc = _normalize_nullable(yaml.safe_load(yaml.safe_dump(openapi_doc)))
    resolver = RefResolver.from_schema(doc)
    schemas = doc.get("components", {}).get("schemas", {})

    def _validate(schema_name: str, payload) -> None:
        assert schema_name in schemas, f"Unknown schema: {schema_name}"
        schema = {"$ref": f"#/components/schemas/{schema_name}"}
        validator = Draft202012Validator(schema, resolver=resolver)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        assert not errors, "; ".join(f"{list(e.path)}: {e.message}" for e in errors)

    return _validate
