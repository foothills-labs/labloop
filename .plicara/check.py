# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.2"]
# ///
"""Plicara contract v1. Canonical copy: project-template/.plicara/check.py.

Vendored deliberately: checking a project never requires a sibling checkout.
Update this file only as an explicit tooling migration.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import urlparse

import yaml

KINDS = {"study", "tool", "benchmark", "dataset", "publication", "collection", "operations"}
STATUSES = {"planned", "active", "maintained", "paused", "completed", "archived"}
REQUIRED = {"schema_version", "id", "name", "description", "kind", "status"}
OPTIONAL = {"repository", "projects", "artifacts", "related", "python", "reason", "resume_when", "readme"}


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently discarding an earlier value."""


def unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("metadata keys must be strings")
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_metadata(root: Path) -> dict:
    data = yaml.load((root / ".plicara/project.yaml").read_text(), Loader=UniqueLoader)
    if not isinstance(data, dict):
        raise ValueError("project.yaml must be a mapping")
    return data


def local_path(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"expected a relative path, got {value!r}")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes project: {value}")
    if not path.exists():
        raise ValueError(f"missing path: {value}")
    return path


def text_field(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def list_field(data: dict, key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return value


def validate(root: Path, *, repository_root: bool = True, seen=None) -> list[tuple[Path, dict]]:
    root = root.resolve()
    seen = {} if seen is None else seen
    data = read_metadata(root)
    missing, unknown = REQUIRED - data.keys(), data.keys() - REQUIRED - OPTIONAL
    if missing or unknown:
        raise ValueError(f"missing fields: {sorted(missing)}; unknown fields: {sorted(unknown)}")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    for key in REQUIRED - {"schema_version"}:
        text_field(data, key)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["id"]):
        raise ValueError("id must be a stable lowercase kebab-case identifier")
    if data["id"] in seen:
        raise ValueError(f"duplicate project id {data['id']}: {seen[data['id']]} and {root}")
    seen[data["id"]] = root
    if data["kind"] not in KINDS or data["status"] not in STATUSES:
        raise ValueError("unrecognized kind or status")
    for key in ("reason", "resume_when"):
        if key in data:
            text_field(data, key)
    if data["status"] in {"paused", "archived"}:
        text_field(data, "reason")
    if data["status"] == "paused":
        text_field(data, "resume_when")
    for path in (data.get("readme", "README.md"), "AGENTS.md", ".plicara/README.md", ".agents/skills/README.md"):
        if not local_path(root, path).is_file():
            raise ValueError(f"expected file: {path}")
    if repository_root:
        for path in ("Makefile", ".plicara/check.py"):
            local_path(root, path)
    if "repository" in data:
        url = urlparse(text_field(data, "repository"))
        if url.scheme != "https" or not url.netloc:
            raise ValueError("repository must be an HTTPS URL")
    for artifact in list_field(data, "artifacts"):
        if not isinstance(artifact, dict) or set(artifact) not in ({"kind", "path"}, {"kind", "url"}):
            raise ValueError("artifacts require kind and exactly one of path or url")
        text_field(artifact, "kind")
        if "path" in artifact:
            local_path(root, artifact["path"])
        else:
            url = urlparse(text_field(artifact, "url"))
            if url.scheme != "https" or not url.netloc:
                raise ValueError("artifact URLs must use HTTPS")
    for relation in list_field(data, "related"):
        if not isinstance(relation, dict) or set(relation) != {"id", "relationship"}:
            raise ValueError("related entries require id and relationship")
        text_field(relation, "id")
        text_field(relation, "relationship")
    for directory in list_field(data, "python"):
        project = local_path(root, directory)
        config = tomllib.loads((project / "pyproject.toml").read_text())
        if not config.get("project", {}).get("requires-python"):
            raise ValueError(f"{directory}: declare requires-python")
        for filename in ("uv.lock", ".python-version"):
            if not (project / filename).is_file():
                raise ValueError(f"{directory}: missing {filename}")
    records = [(root, data)]
    children = list_field(data, "projects")
    if children and data["kind"] != "collection":
        raise ValueError("only a collection may declare projects")
    for child in children:
        path = local_path(root, child)
        if path == root:
            raise ValueError("a project cannot contain itself")
        records.extend(validate(path, repository_root=False, seen=seen))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        records = validate(args.root)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Plicara contract failed: {error}", file=sys.stderr)
        return 1
    print(f"Plicara contract OK: {len(records)} project(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
