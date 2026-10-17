from typing import Any
from .catalog import CATALOG
from .vocabulary import PROFILES

def node_template(node: dict[str, Any]) -> dict:
    return node.get("template") or CATALOG[node["type"]]

def profile_required(node: dict[str, Any]) -> list[str]:
    required = list(node_template(node)["required"])
    extra = str(node.get("config", {}).get("required_fields", ""))
    for field in [x.strip() for x in extra.split(",") if x.strip()]:
        if field not in required:
            required.append(field)
    return required

def profile_iri(node: dict[str, Any]) -> str:
    explicit = str(node.get("config", {}).get("profile_uri", "")).strip()
    return explicit or node_template(node).get("shape") or str(PROFILES[node_template(node)["profile"]])
