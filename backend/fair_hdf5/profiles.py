from typing import Any
from .catalog import CATALOG
from .vocabulary import PROFILES

def profile_required(node: dict[str, Any]) -> list[str]:
    required = list(CATALOG[node["type"]]["required"])
    extra = str(node.get("config", {}).get("required_fields", ""))
    for field in [x.strip() for x in extra.split(",") if x.strip()]:
        if field not in required:
            required.append(field)
    return required

def profile_iri(node: dict[str, Any]) -> str:
    explicit = str(node.get("config", {}).get("profile_uri", "")).strip()
    return explicit or str(PROFILES[CATALOG[node["type"]]["profile"]])
