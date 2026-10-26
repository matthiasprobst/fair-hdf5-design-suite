"""Built-in input nodes and data bindings, independent of SHACL templates."""

from .errors import DesignError

CSV_SOURCE = "csv_source"
CSV_INFO = {"kind": None, "required": [], "fields": [], "label": "CSV Source"}
CSV_DEFAULTS = {
    "delimiter": ",",
    "decimal_separator": ".",
    "has_header": True,
    "filename": "",
    "columns": [],
}


def validate_source(config):
    if not isinstance(config, dict) or set(config) - CSV_DEFAULTS.keys():
        raise DesignError("Unsupported CSV source configuration.")
    options = {**CSV_DEFAULTS, **config}
    if (
        options["delimiter"] not in {",", ";", "\t"}
        or options["decimal_separator"] not in {".", ","}
        or options["delimiter"] == options["decimal_separator"]
        or type(options["has_header"]) is not bool
        or not isinstance(options["filename"], str)
        or len(options["filename"]) > 512
        or "\x00" in options["filename"]
        or not isinstance(options["columns"], list)
        or any(not isinstance(c, str) or "\x00" in c for c in options["columns"])
    ):
        raise DesignError("Invalid CSV settings, filename, or column headers.")
    return options


def validate_data_edges(design):
    from .profiles import node_template

    nodes = {n["id"]: n for n in design["nodes"]}
    targets = set()
    for edge in design.get("edges", []):
        if edge.get("kind") not in (None, "data"):
            raise DesignError("Unknown connection kind.")
        source, target = nodes.get(edge["source"]), nodes.get(edge["target"])
        if not source or not target:
            raise DesignError("Every edge must connect existing nodes.")
        if edge.get("kind") == "data":
            if (
                source["type"] != CSV_SOURCE
                or node_template(target)["kind"] != "dataset"
                or target["id"] in targets
                or "predicate" in edge
                or "field_id" in edge
                or type(edge.get("column_index")) is not int
                or edge["column_index"] < 0
            ):
                raise DesignError(
                    "Data connections require a CSV column and one input per dataset."
                )
            targets.add(target["id"])
        elif source["type"] == CSV_SOURCE or target["type"] == CSV_SOURCE:
            raise DesignError("CSV sources only support data connections to datasets.")
        elif "column_index" in edge:
            raise DesignError("Column mappings require a data connection.")
