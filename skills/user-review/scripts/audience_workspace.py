#!/usr/bin/env python3
"""user-review 私人 Audience Workspace 的确定性数据层。"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


WORKSPACE_SCHEMA = "user-review-workspace/v1"
PANELS_SCHEMA = "user-review-panels/v1"
CATALOG_SCHEMA = "user-review-persona-catalog/v1"
PLAN_SCHEMA = "user-review-change-plan/v1"
RECORD_SCHEMA = "user-review-change-record/v1"
LIFECYCLE = {"candidate", "reusable", "retired"}
RELATIONSHIPS = {"core", "adjacent", "challenge", "non_target"}
KNOWLEDGE_STAGES = {"unaware", "aware", "problem_solving", "experienced"}
PROVENANCE = {"grounded", "inferred", "operator_hypothesis", "synthetic"}
CONFIDENCE = {"low", "medium", "high"}
VALIDATION_STATUS = {"unvalidated", "partially_validated", "validated"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class WorkspaceError(ValueError):
    """Audience Workspace 契约或事务失败。"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def record_id(prefix: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{stamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError(f"无法读取 UTF-8 文件：{path}：{exc}") from exc


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"JSON 无效：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError(f"JSON 根节点必须是对象：{path}")
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise WorkspaceError(f"无法计算文件哈希：{path}：{exc}") from exc


def digest_or_none(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def write_atomic(path: Path, data: bytes, suffix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{suffix}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def write_json(path: Path, value: Any) -> None:
    write_atomic(path, json_bytes(value), "write")


def ensure_outside(path: Path, skill_root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(skill_root.resolve())
    except ValueError:
        return
    raise WorkspaceError(f"{label}不得位于 Skill 安装目录内")


def validate_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise WorkspaceError(f"{label} ID 无效：{value}")
    return value


def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        raise WorkspaceError(f"Persona 版本必须使用 x.y.z：{value}")
    return tuple(int(part) for part in match.groups())


def next_patch(value: str) -> str:
    major, minor, patch = version_tuple(value)
    return f"{major}.{minor}.{patch + 1}"


def parse_frontmatter_text(text: str) -> tuple[dict[str, str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise WorkspaceError("Persona 缺少 YAML frontmatter")
    meta: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, lines[index + 1:]
        if line.strip() and not line.lstrip().startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    raise WorkspaceError("Persona YAML frontmatter 未闭合")


def validate_persona_text(text: str, expected_id: str | None = None) -> dict[str, str]:
    meta, _ = parse_frontmatter_text(text)
    required = {"id", "version", "provenance", "confidence", "validation_status"}
    missing = sorted(required - meta.keys())
    if missing:
        raise WorkspaceError(f"Persona 缺少字段：{missing}")
    validate_id(meta["id"], "Persona")
    version_tuple(meta["version"])
    if expected_id and meta["id"] != expected_id:
        raise WorkspaceError(f"Persona ID 不匹配：{expected_id} != {meta['id']}")
    if meta["provenance"] not in PROVENANCE or meta["confidence"] not in CONFIDENCE:
        raise WorkspaceError("Persona 来源或置信度无效")
    if meta["validation_status"] not in VALIDATION_STATUS:
        raise WorkspaceError("Persona 验证状态无效")
    return meta


def replace_frontmatter(text: str, updates: dict[str, str]) -> str:
    meta, body = parse_frontmatter_text(text)
    meta.update(updates)
    ordered = ["id", "version", "provenance", "confidence", "validation_status", "derived_from"]
    keys = [key for key in ordered if key in meta] + sorted(set(meta) - set(ordered))
    header = ["---", *[f"{key}: {meta[key]}" for key in keys], "---", ""]
    return "\n".join(header + body).rstrip() + "\n"


def load_builtin_catalog(skill_root: Path) -> dict[str, Any]:
    path = skill_root / "references" / "personas" / "catalog.json"
    value = read_json(path)
    if value.get("schema_version") != "2.0" or not isinstance(value.get("personas"), dict):
        raise WorkspaceError("内置 Persona 目录无效")
    personas: dict[str, Any] = {}
    for persona_id, raw in value["personas"].items():
        entry = dict(raw)
        persona_path = path.parent / entry["file"]
        validate_persona_text(read_text(persona_path), persona_id)
        entry["source"] = "builtin"
        entry["path"] = str(persona_path.resolve())
        personas[persona_id] = entry
    return {"personas": personas, "path": str(path)}


def demo_workspace_path(skill_root: Path) -> Path:
    return skill_root / "references" / "demo-workspace"


def resolve_workspace_path(
    skill_root: Path,
    explicit_path: Path | None = None,
    data_home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[Path, str]:
    if explicit_path:
        return explicit_path.expanduser().resolve(), "workspace"
    environment = os.environ if environ is None else environ
    configured = environment.get("USER_REVIEW_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve(), "workspace"
    home = (data_home or (Path.home() / ".user-review")).expanduser().resolve()
    index = home / "index.json"
    if index.is_file():
        value = read_json(index)
        active = value.get("active_workspace")
        if isinstance(active, str) and active:
            return Path(active).expanduser().resolve(), "workspace"
    return demo_workspace_path(skill_root).resolve(), "builtin"


def validate_workspace(skill_root: Path, workspace_path: Path) -> dict[str, Any]:
    manifest_path = workspace_path / "workspace.json"
    manifest = read_json(manifest_path)
    if manifest.get("schema") != WORKSPACE_SCHEMA:
        raise WorkspaceError("Workspace schema 无效")
    validate_id(manifest.get("id"), "Workspace")
    if manifest.get("storage") not in {"builtin_read_only", "private"}:
        raise WorkspaceError("Workspace storage 无效")
    panels_path = workspace_path / str(manifest.get("panels_file", "panels.json"))
    panels = read_json(panels_path)
    if panels.get("schema") != PANELS_SCHEMA or not isinstance(panels.get("panels"), dict):
        raise WorkspaceError("Panels schema 无效")
    default_id = panels.get("default_panel")
    if default_id not in panels["panels"] or panels["panels"][default_id].get("kind") != "base":
        raise WorkspaceError("默认 Panel 无效")

    builtin = load_builtin_catalog(skill_root)["personas"]
    private: dict[str, Any] = {}
    catalog_path = (workspace_path / str(manifest["persona_catalog"])).resolve()
    if manifest["storage"] == "private":
        ensure_outside(workspace_path, skill_root, "私人 Workspace")
        catalog = read_json(catalog_path)
        if catalog.get("schema") != CATALOG_SCHEMA or not isinstance(catalog.get("personas"), dict):
            raise WorkspaceError("私人 Persona 目录无效")
        for persona_id, raw in catalog["personas"].items():
            if persona_id in builtin:
                raise WorkspaceError(f"私人 Persona 不得覆盖内置 ID：{persona_id}")
            entry = dict(raw)
            persona_path = catalog_path.parent / entry["file"]
            meta = validate_persona_text(read_text(persona_path), persona_id)
            for key in ("version", "provenance", "confidence", "validation_status"):
                if entry.get(key) != meta[key]:
                    raise WorkspaceError(f"私人 Persona 的 {key} 与文件不一致：{persona_id}")
            if entry.get("lifecycle") not in LIFECYCLE:
                raise WorkspaceError(f"Persona lifecycle 无效：{persona_id}")
            entry["source"] = "workspace"
            entry["path"] = str(persona_path.resolve())
            private[persona_id] = entry
    elif catalog_path != (skill_root / "references" / "personas" / "catalog.json").resolve():
        raise WorkspaceError("只读示范必须引用内置 Persona 目录")

    merged = dict(builtin)
    merged.update(private)
    for panel_id, panel in panels["panels"].items():
        if panel.get("kind") == "base":
            ids = panel.get("persona_ids")
        elif panel.get("kind") == "scenario":
            ids = list(panel.get("add_persona_ids", [])) + list(panel.get("remove_persona_ids", []))
            if panel.get("base") not in panels["panels"]:
                raise WorkspaceError(f"场景 Panel 引用未知 base：{panel_id}")
        else:
            raise WorkspaceError(f"Panel kind 无效：{panel_id}")
        if not isinstance(ids, list) or any(item not in merged for item in ids):
            raise WorkspaceError(f"Panel 引用了未知 Persona：{panel_id}")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "panels": panels,
        "panels_path": panels_path,
        "catalog_path": catalog_path,
        "builtin_personas": builtin,
        "private_personas": private,
        "personas": merged,
        "workspace_path": workspace_path,
    }


def load_workspace(
    skill_root: Path,
    explicit_path: Path | None = None,
    data_home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    path, source = resolve_workspace_path(skill_root, explicit_path, data_home, environ)
    view = validate_workspace(skill_root, path)
    view["source"] = source
    return view


def workspace_summary(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": view["manifest"]["schema"],
        "id": view["manifest"]["id"],
        "name": view["manifest"]["name"],
        "source": view["source"],
        "storage": view["manifest"]["storage"],
        "workspace": str(view["workspace_path"]),
        "builtin_personas": len(view["builtin_personas"]),
        "private_personas": len(view["private_personas"]),
        "panels": sorted(view["panels"]["panels"]),
    }


def proposed_json(value: Any) -> dict[str, Any]:
    return {"format": "json", "content": value}


def proposed_text(value: str) -> dict[str, Any]:
    return {"format": "text", "content": value}


def write_plan(plan_path: Path, plan: dict[str, Any], skill_root: Path) -> dict[str, Any]:
    ensure_outside(plan_path, skill_root, "私人变更计划")
    write_json(plan_path, plan)
    return {"plan": str(plan_path), "plan_sha256": sha256_file(plan_path), "preview": plan}


def base_plan(operation: str, workspace: Path, record_root: Path) -> dict[str, Any]:
    value_id = record_id(operation.replace("_", "-"))
    return {
        "schema": PLAN_SCHEMA,
        "operation": operation,
        "record_id": value_id,
        "created_at": utc_now(),
        "workspace": str(workspace.resolve()),
        "record_root": str(record_root.resolve()),
        "before": {},
        "sources": {},
        "proposed_files": {},
        "impact": {},
    }


def build_workspace_plan(skill_root: Path, data_home: Path, seed_path: Path, plan_path: Path) -> dict[str, Any]:
    seed = read_json(seed_path)
    if seed.get("schema") != "user-review-workspace-seed/v1":
        raise WorkspaceError("Workspace seed schema 无效")
    workspace_id = validate_id(seed.get("id"), "Workspace")
    data_home = data_home.expanduser().resolve()
    ensure_outside(data_home, skill_root, "私人数据目录")
    target = data_home / "workspaces" / workspace_id
    if target.exists():
        raise WorkspaceError(f"Workspace 已存在：{target}")
    demo_panels = read_json(demo_workspace_path(skill_root) / "panels.json")
    now = utc_now()
    manifest = {
        "schema": WORKSPACE_SCHEMA,
        "id": workspace_id,
        "name": str(seed.get("name", "")).strip(),
        "storage": "private",
        "offering": str(seed.get("offering", "")).strip(),
        "audience_promise": str(seed.get("audience_promise", "")).strip(),
        "persona_catalog": "personas/catalog.json",
        "panels_file": "panels.json",
        "created_at": now,
        "updated_at": now,
    }
    if not all(manifest[key] for key in ("name", "offering", "audience_promise")):
        raise WorkspaceError("Workspace 名称、业务和受众承诺不能为空")
    catalog = {"schema": CATALOG_SCHEMA, "personas": {}}
    index_path = data_home / "index.json"
    index = read_json(index_path) if index_path.is_file() else {"schema": "user-review-index/v1", "workspaces": {}}
    index.setdefault("workspaces", {})[workspace_id] = {"name": manifest["name"], "path": str(target)}
    index["active_workspace"] = str(target)
    plan = base_plan("workspace_create", target, target)
    plan["validation_skill_root"] = str(skill_root.resolve())
    plan["sources"] = {str(seed_path.resolve()): sha256_file(seed_path)}
    plan["before"] = {
        str(target / "workspace.json"): None,
        str(target / "personas" / "catalog.json"): None,
        str(target / "panels.json"): None,
        str(index_path): digest_or_none(index_path),
    }
    plan["proposed_files"] = {
        str(target / "workspace.json"): proposed_json(manifest),
        str(target / "personas" / "catalog.json"): proposed_json(catalog),
        str(target / "panels.json"): proposed_json(demo_panels),
        str(index_path): proposed_json(index),
    }
    plan["impact"] = {"creates_workspace": workspace_id, "activates_workspace": True, "private_personas": 0}
    return write_plan(plan_path, plan, skill_root)


def entry_from_source(raw: dict[str, Any], meta: dict[str, str], current: dict[str, Any] | None = None) -> dict[str, Any]:
    required = {
        "name", "summary", "segment", "role", "domains", "content_types", "platforms",
        "content_relationship", "knowledge_stage", "reading_context", "job_to_be_done",
        "pains", "constraints", "trust_signals", "rejection_signals", "language_cues", "lifecycle",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise WorkspaceError(f"长期 Persona 条目缺少字段：{missing}")
    if raw["content_relationship"] not in RELATIONSHIPS or raw["knowledge_stage"] not in KNOWLEDGE_STAGES:
        raise WorkspaceError("Persona 关系或知识阶段无效")
    if raw["lifecycle"] not in LIFECYCLE:
        raise WorkspaceError("Persona lifecycle 无效")
    now = utc_now()
    value = dict(raw)
    value.update({
        "file": f"{meta['id']}.md",
        "version": meta["version"],
        "provenance": meta["provenance"],
        "confidence": meta["confidence"],
        "validation_status": meta["validation_status"],
        "created_at": current.get("created_at", now) if current else now,
        "updated_at": now,
    })
    return value


def affected_panels(panels: dict[str, Any], persona_id: str) -> list[str]:
    result = []
    for panel_id, panel in panels["panels"].items():
        ids = list(panel.get("persona_ids", [])) + list(panel.get("add_persona_ids", [])) + list(panel.get("remove_persona_ids", []))
        if persona_id in ids:
            result.append(panel_id)
    return sorted(result)


def build_persona_plan(
    skill_root: Path,
    workspace: Path,
    operation: str,
    plan_path: Path,
    persona_path: Path | None = None,
    entry_path: Path | None = None,
    persona_id: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    view = validate_workspace(skill_root, workspace.resolve())
    if view["manifest"]["storage"] != "private":
        raise WorkspaceError("内置示范只读；请先创建私人 Workspace")
    catalog = read_json(view["catalog_path"])
    proposed_catalog = json.loads(json.dumps(catalog, ensure_ascii=False))
    proposed: dict[str, Any] = {}
    sources: dict[str, str] = {}

    if operation in {"add", "update", "derive"}:
        if not persona_path or not entry_path:
            raise WorkspaceError(f"{operation} 需要 Persona 文件和目录条目")
        persona_text = read_text(persona_path)
        meta = validate_persona_text(persona_text)
        persona_id = meta["id"]
        raw_entry = read_json(entry_path)
        sources = {str(persona_path.resolve()): sha256_file(persona_path), str(entry_path.resolve()): sha256_file(entry_path)}
        if operation == "add":
            if persona_id in view["builtin_personas"]:
                raise WorkspaceError(f"私人 Persona 不得覆盖内置 ID：{persona_id}；请使用 derive")
            if persona_id in view["private_personas"]:
                raise WorkspaceError(f"私人 Persona 已存在：{persona_id}")
            entry = entry_from_source(raw_entry, meta)
        elif operation == "update":
            current = view["private_personas"].get(persona_id)
            if not current:
                raise WorkspaceError(f"只能更新私人 Persona：{persona_id}")
            if version_tuple(meta["version"]) <= version_tuple(current["version"]):
                raise WorkspaceError("更新 Persona 时版本必须递增")
            entry = entry_from_source(raw_entry, meta, current)
        else:
            if not source_id or source_id not in view["personas"]:
                raise WorkspaceError("derive 需要有效的 source-id")
            if persona_id in view["personas"]:
                raise WorkspaceError(f"派生 Persona 必须使用新 ID：{persona_id}")
            entry = entry_from_source(raw_entry, meta)
            entry["derived_from"] = source_id
            persona_text = replace_frontmatter(persona_text, {"derived_from": source_id})
        proposed_catalog["personas"][persona_id] = entry
        target = view["catalog_path"].parent / f"{persona_id}.md"
        proposed[str(target)] = proposed_text(persona_text)
    elif operation in {"retire", "restore"}:
        persona_id = validate_id(persona_id, "Persona")
        current = view["private_personas"].get(persona_id)
        if not current:
            raise WorkspaceError(f"只能维护私人 Persona：{persona_id}")
        target = Path(current["path"])
        current_text = read_text(target)
        new_version = next_patch(current["version"])
        new_lifecycle = "retired" if operation == "retire" else "candidate"
        if operation == "retire" and current["lifecycle"] == "retired":
            raise WorkspaceError("Persona 已停用")
        if operation == "restore" and current["lifecycle"] != "retired":
            raise WorkspaceError("只有 retired Persona 可以恢复")
        entry = dict(catalog["personas"][persona_id])
        entry.update({"version": new_version, "lifecycle": new_lifecycle, "updated_at": utc_now()})
        proposed_catalog["personas"][persona_id] = entry
        proposed[str(target)] = proposed_text(replace_frontmatter(current_text, {"version": new_version}))
    else:
        raise WorkspaceError(f"不支持的 Persona 操作：{operation}")

    proposed[str(view["catalog_path"])] = proposed_json(proposed_catalog)
    plan = base_plan(f"persona_{operation}", workspace, workspace)
    plan["validation_skill_root"] = str(skill_root.resolve())
    plan["sources"] = sources
    plan["before"] = {path: digest_or_none(Path(path)) for path in proposed}
    plan["proposed_files"] = proposed
    plan["impact"] = {
        "persona_id": persona_id,
        "affected_panels": affected_panels(view["panels"], persona_id),
        "operation": operation,
    }
    return write_plan(plan_path, plan, skill_root)


def build_panel_plan(skill_root: Path, workspace: Path, patch_path: Path, plan_path: Path) -> dict[str, Any]:
    view = validate_workspace(skill_root, workspace.resolve())
    if view["manifest"]["storage"] != "private":
        raise WorkspaceError("内置示范只读；请先创建私人 Workspace")
    patch = read_json(patch_path)
    if patch.get("schema") != "user-review-panel-patch/v1":
        raise WorkspaceError("Panel patch schema 无效")
    scenario = validate_id(patch.get("scenario"), "Panel")
    add_ids = patch.get("add_persona_ids", [])
    remove_ids = patch.get("remove_persona_ids", [])
    if not isinstance(add_ids, list) or not isinstance(remove_ids, list):
        raise WorkspaceError("Panel add/remove 必须是数组")
    unknown = sorted((set(add_ids) | set(remove_ids)) - set(view["personas"]))
    if unknown:
        raise WorkspaceError(f"Panel 引用了未知 Persona：{unknown}")
    panels = json.loads(json.dumps(view["panels"], ensure_ascii=False))
    if scenario == panels["default_panel"]:
        raise WorkspaceError("默认 Panel 请使用完整 persona_ids 变更，不接受场景 patch")
    panels["panels"][scenario] = {
        "kind": "scenario",
        "label": str(patch.get("label", scenario)),
        "description": str(patch.get("description", "")),
        "base": panels["default_panel"],
        "add_persona_ids": add_ids,
        "remove_persona_ids": remove_ids,
        "required_relationships": patch.get("required_relationships", ["core"]),
    }
    plan = base_plan("panel_update", workspace, workspace)
    plan["validation_skill_root"] = str(skill_root.resolve())
    plan["sources"] = {str(patch_path.resolve()): sha256_file(patch_path)}
    plan["before"] = {str(view["panels_path"]): sha256_file(view["panels_path"])}
    plan["proposed_files"] = {str(view["panels_path"]): proposed_json(panels)}
    plan["impact"] = {"scenario": scenario, "add": add_ids, "remove": remove_ids}
    return write_plan(plan_path, plan, skill_root)


def resolve_panel(view: dict[str, Any], scenario: str | None = None) -> tuple[str, list[str], list[str]]:
    panels = view["panels"]
    panel_id = scenario or panels["default_panel"]
    if panel_id not in panels["panels"]:
        raise WorkspaceError(f"未知场景 Panel：{panel_id}")
    panel = panels["panels"][panel_id]
    if panel["kind"] == "base":
        ids = list(panel["persona_ids"])
    else:
        base = panels["panels"][panel["base"]]
        ids = [item for item in base["persona_ids"] if item not in panel.get("remove_persona_ids", [])]
        ids.extend(item for item in panel.get("add_persona_ids", []) if item not in ids)
    ids = [item for item in ids if view["personas"][item].get("lifecycle") != "retired"]
    required = list(panel.get("required_relationships", ["core"]))
    return panel_id, ids, required


def recommend_panel(skill_root: Path, workspace: Path | None, scenario: str | None) -> dict[str, Any]:
    view = load_workspace(skill_root, workspace)
    panel_id, ids, required = resolve_panel(view, scenario)
    candidates = []
    coverage = set()
    for persona_id in ids:
        entry = view["personas"][persona_id]
        relationship = entry["content_relationship"]
        coverage.add(relationship)
        reasons = [f"进入 {panel_id} 评审团", f"提供 {relationship} 视角"]
        candidates.append({
            "id": persona_id,
            "name": entry["name"],
            "source": entry["source"],
            "relationship": relationship,
            "knowledge_stage": entry["knowledge_stage"],
            "reasons": reasons,
        })
    gaps = sorted(set(required) - coverage)
    return {
        "workspace": workspace_summary(view),
        "scenario": panel_id,
        "candidates": candidates,
        "coverage": sorted(coverage),
        "gaps": gaps,
        "needs_run_local_persona": bool(gaps),
    }


def panel_persona_files(skill_root: Path, workspace: Path, scenario: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    view = load_workspace(skill_root, workspace)
    panel_id, ids, _ = resolve_panel(view, scenario)
    selected = []
    for persona_id in ids:
        entry = view["personas"][persona_id]
        selected.append({"id": persona_id, "path": Path(entry["path"]), "entry": entry, "run_local": False})
    view["resolved_scenario"] = panel_id
    return view, selected


def materialize_proposed(value: dict[str, Any]) -> bytes:
    if value.get("format") == "json":
        return json_bytes(value.get("content"))
    if value.get("format") == "text" and isinstance(value.get("content"), str):
        return value["content"].encode("utf-8")
    raise WorkspaceError("计划包含无效 proposed file")


def apply_change_plan(plan_path: Path, expected_hash: str) -> dict[str, Any]:
    actual_hash = sha256_file(plan_path)
    if actual_hash != expected_hash:
        raise WorkspaceError("计划哈希不匹配；请重新预览")
    plan = read_json(plan_path)
    if plan.get("schema") != PLAN_SCHEMA:
        raise WorkspaceError("变更计划 schema 无效")
    for raw, expected in plan.get("sources", {}).items():
        path = Path(raw)
        if not path.is_file() or sha256_file(path) != expected:
            raise WorkspaceError(f"输入源已漂移；请重新预览：{path}")
    for raw, expected in plan.get("before", {}).items():
        path = Path(raw)
        if digest_or_none(path) != expected:
            raise WorkspaceError(f"目标状态已漂移；请重新预览：{path}")

    workspace = Path(plan["workspace"])
    record_root = Path(plan["record_root"])
    proposed = {Path(raw): materialize_proposed(value) for raw, value in plan["proposed_files"].items()}
    originals = {path: path.read_bytes() if path.is_file() else None for path in proposed}
    backup_dir = record_root / "backups" / plan["record_id"]
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path, data in originals.items():
        if data is not None:
            backup = backup_dir / sha256_bytes(str(path).encode("utf-8"))
            backup.write_bytes(data)
    try:
        for path, data in proposed.items():
            write_atomic(path, data, plan["record_id"])
        validation_root = plan.get("validation_skill_root")
        validate_workspace(Path(validation_root) if validation_root else _infer_skill_root(plan), workspace)
        record = {
            "schema": RECORD_SCHEMA,
            "record_id": plan["record_id"],
            "operation": plan["operation"],
            "applied_at": utc_now(),
            "plan": str(plan_path),
            "plan_sha256": actual_hash,
            "changed_files": [str(path) for path in proposed],
            "before": plan["before"],
            "after": {str(path): sha256_file(path) for path in proposed},
            "backup_dir": str(backup_dir),
            "impact": plan.get("impact", {}),
        }
        record_path = record_root / "change-records" / f"{plan['record_id']}.json"
        write_json(record_path, record)
    except Exception:
        for path, data in reversed(list(originals.items())):
            if data is None:
                path.unlink(missing_ok=True)
            else:
                write_atomic(path, data, "rollback")
        if plan["operation"] == "workspace_create" and workspace.exists():
            for child in sorted(workspace.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    try:
                        child.rmdir()
                    except OSError:
                        pass
            try:
                workspace.rmdir()
            except OSError:
                pass
        raise
    return {"status": "applied", "operation": plan["operation"], "record": str(record_path), "workspace": str(workspace)}


def _infer_skill_root(plan: dict[str, Any]) -> Path:
    for raw in plan.get("sources", {}):
        path = Path(raw)
        parts = path.parts
        if "skills" in parts and "user-review" in parts:
            index = parts.index("user-review")
            return Path(*parts[:index + 1])
    skill_root = plan.get("validation_skill_root")
    if skill_root:
        return Path(skill_root)
    raise WorkspaceError("计划缺少 Skill 根目录，无法完成写后验证")
