"""Read-only validation and index preview for Project Finder schemas v1/v2."""
import argparse
from datetime import date
import json
from pathlib import Path, PureWindowsPath
import re
import sys
from urllib.parse import quote

try:
    import yaml
except ImportError:
    raise SystemExit("PyYAML is unavailable. Use the manual checks in maintenance.md.")

KINDS_V1 = {"implementation", "fix", "convention", "decision"}
KINDS = KINDS_V1 | {"run", "lesson", "workflow"}
STATUSES = {"candidate", "active", "stale", "deprecated"}
IDENTIFIER = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")


def inspect(root):
    root = Path(root).resolve()
    errors, warnings, records = [], [], []

    def read_yaml(path, frontmatter=False):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("symlink or path outside library")
        content = path.read_text(encoding="utf-8-sig")
        if frontmatter:
            match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.S)
            if not match:
                raise ValueError("missing YAML frontmatter")
            content = match.group(1)
        value = yaml.safe_load(content)
        if not isinstance(value, dict):
            raise ValueError("expected YAML mapping")
        return value

    try:
        config = read_yaml(root / "config.yaml")
        if type(config.get("schema_version")) is not int or config["schema_version"] not in (1, 2):
            raise ValueError("unsupported config schema_version")
        projects = config.get("projects")
        if not isinstance(projects, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip()
            for k, v in projects.items()
        ):
            raise ValueError("projects must map names to nonempty paths")
        for key in ("shared_libraries", "exclude"):
            values = config.get(key, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError(key + " must be a list of strings")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return {"errors": ["config: " + str(exc)], "warnings": [], "records": []}

    for path in sorted((root / "memories").rglob("*.md")):
        label = path.relative_to(root).as_posix()
        try:
            item = read_yaml(path, True)
            required = {"schema_version", "id", "kind", "title", "status", "scope",
                        "tags", "created", "updated", "sources", "supersedes"}
            if required - item.keys():
                raise ValueError("missing fields: " + ", ".join(sorted(required - item.keys())))
            if type(item["schema_version"]) is not int or item["schema_version"] not in (1, 2):
                raise ValueError("unsupported record schema_version")
            if item["schema_version"] > config["schema_version"]:
                raise ValueError("record version exceeds config version")
            if not isinstance(item["id"], str) or not IDENTIFIER.fullmatch(item["id"]):
                raise ValueError("invalid id")
            if not isinstance(item["kind"], str) or item["kind"] not in KINDS:
                raise ValueError("invalid kind")
            if item["schema_version"] == 1 and item["kind"] not in KINDS_V1:
                raise ValueError("new record kinds require schema v2")
            if path.relative_to(root).parts[1] != item["kind"]:
                raise ValueError("directory must match kind")
            if not isinstance(item["status"], str) or item["status"] not in STATUSES:
                raise ValueError("invalid status")
            if item["scope"] not in ("project", "cross-project"):
                raise ValueError("invalid scope")
            if not isinstance(item["title"], str) or not item["title"].strip():
                raise ValueError("title must be nonempty")
            for key in ("tags", "supersedes"):
                if not isinstance(item[key], list) or not all(isinstance(v, str) for v in item[key]):
                    raise ValueError(key + " must be a list of strings")
            for key in ("created", "updated"):
                date.fromisoformat(str(item[key]))
            if str(item["updated"]) < str(item["created"]):
                raise ValueError("updated precedes created")
            if not isinstance(item["sources"], list):
                raise ValueError("sources must be a list")
            if item["kind"] in ("run", "lesson", "workflow"):
                for key in ("context", "verification"):
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        raise ValueError(key + " must describe scope or verification")
                if not isinstance(item.get("related"), list) or not all(
                    isinstance(v, str) for v in item["related"]
                ):
                    raise ValueError("related must be a list of IDs")
            if item["kind"] == "run":
                if item.get("outcome") not in ("passed", "failed", "partial", "unverified"):
                    raise ValueError("invalid run outcome")
            if item["kind"] == "workflow":
                for key in ("inputs", "steps", "acceptance"):
                    if not isinstance(item.get(key), list) or not item[key] or not all(
                        isinstance(v, str) and v.strip() for v in item[key]
                    ):
                        raise ValueError(key + " must be a nonempty list of strings")
            for source in item["sources"]:
                if not isinstance(source, dict) or not isinstance(source.get("project"), str):
                    raise ValueError("source requires project")
                if source["project"] not in projects:
                    raise ValueError("unknown source project: " + source["project"])
                raw = source.get("path")
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError("source requires path")
                normalized = raw.replace("\\", "/")
                if (normalized.startswith("/") or PureWindowsPath(raw).drive
                        or ".." in normalized.split("/")):
                    raise ValueError("source path must stay relative to its project")
            item["_path"] = label
            records.append(item)
        except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
            errors.append(label + ": " + str(exc))

    by_id = {}
    for item in records:
        if item["id"] in by_id:
            errors.append("duplicate id: " + item["id"])
        by_id[item["id"]] = item
    graph = {}
    for item in records:
        for target in item.get("related", []):
            if "::" in target:
                parts = target.split("::")
                if len(parts) != 2 or not all(IDENTIFIER.fullmatch(p) for p in parts):
                    errors.append("invalid related reference: " + target)
                else:
                    warnings.append("external reference not verified: " + target)
            elif target not in by_id:
                errors.append(item["id"] + ": missing related id " + target)
        if item["kind"] == "workflow" and item["status"] == "active":
            supporting = [
                by_id.get(target, {}) for target in item.get("related", [])
            ]
            if not any(r.get("kind") == "run" and r.get("outcome") == "passed"
                       and r.get("status") == "active"
                       and item["id"] in r.get("related", [])
                       for r in supporting):
                errors.append(item["id"] + ": active workflow requires a linked active passed run pointing back to it")
        graph[item["id"]] = []
        for target in item["supersedes"]:
            if "::" in target:
                parts = target.split("::")
                if len(parts) != 2 or not all(IDENTIFIER.fullmatch(p) for p in parts):
                    errors.append("invalid cross-library reference: " + target)
                else:
                    warnings.append("external reference not verified: " + target)
            elif target not in by_id:
                errors.append(item["id"] + ": missing superseded id " + target)
            else:
                graph[item["id"]].append(target)
                if by_id[target]["status"] != "deprecated":
                    warnings.append(target + ": superseded but not deprecated")
    # Iterative traversal avoids recursion limits on large libraries.
    done = set()
    for start in graph:
        pending = [(start, False)]
        active = set()
        while pending:
            node, leaving = pending.pop()
            if leaving:
                active.discard(node)
                done.add(node)
            elif node in active:
                errors.append("supersedes cycle involving " + node)
            elif node not in done:
                active.add(node)
                pending.append((node, True))
                pending.extend((child, False) for child in graph[node])
    return {"errors": errors, "warnings": warnings, "records": records}


def render_index(records):
    def cell(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# 开发记忆索引", "", "适用条件与验证范围以记录正文为准。", "",
             "| ID | 标题 | 类型 | 标签 | 状态 | 记录 |",
             "|---|---|---|---|---|---|"]
    for item in sorted(records, key=lambda row: row["id"]):
        values = [item["id"], item["title"], item["kind"], ", ".join(item["tags"]), item["status"]]
        lines.append("| " + " | ".join(map(cell, values)) +
                     " | [记录](" + quote(item["_path"], safe="/.-") + ") |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--index", action="store_true", help="print index preview; never write files")
    args = parser.parse_args()
    result = inspect(args.library)
    if args.index and not result["errors"]:
        print(render_index(result["records"]), end="")
        for warning in result["warnings"]:
            print(warning, file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
