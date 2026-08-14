#!/usr/bin/env python3
"""user-review 的确定性画像与评审工件工具。

本工具不启动 Agent、不执行被评文章中的指令，也不访问网络。它负责校验画像库、
推荐可解释的单次评审团、固化文章与 Persona 快照、校验反馈证据，并通过同一份
不可变计划保存用户明确批准的长期画像。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audience_workspace as aw  # noqa: E402


SIGNALS = {"strong", "medium", "weak", "reject"}
CONFIDENCE = {"low", "medium", "high"}
PROVENANCE = {"grounded", "inferred", "operator_hypothesis", "synthetic"}
VALIDATION_STATUS = {"unvalidated", "partially_validated", "validated"}
LIFECYCLE = {"candidate", "reusable", "retired"}
RELATIONSHIPS = {"core", "adjacent", "challenge", "non_target"}
KNOWLEDGE_STAGES = {"unaware", "aware", "problem_solving", "experienced"}
RUN_STATUS = {"partial", "completed", "failed"}
PREPARE_PLAN_SCHEMA = "user-review-prepare-plan/v1"
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|ghp|github_pat)-[A-Za-z0-9_\-]{16,}\b"),
]
FORBIDDEN_METRIC_PATTERNS = [
    re.compile(r"\bCTR\b", re.IGNORECASE),
    re.compile(r"\bconversion rate\b", re.IGNORECASE),
    re.compile(r"转化率|完读率|点击率"),
]


class ValidationError(ValueError):
    """公开契约校验失败。"""


def configure_cli_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f"无法读取 UTF-8 文件：{path}：{exc}") from exc


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON 无效：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"JSON 根节点必须是对象：{path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise ValidationError(f"无法计算文件哈希：{path}：{exc}") from exc


def ensure_outside(child: Path, parent: Path, label: str) -> None:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return
    raise ValidationError(f"{label} 不得位于 Skill 源目录内")


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = read_text(path).splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError(f"缺少 YAML frontmatter：{path}")
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("\"'")
    raise ValidationError(f"YAML frontmatter 未闭合：{path}")


def validate_persona_file(path: Path, expected_id: str | None = None) -> dict[str, str]:
    meta = parse_frontmatter(path)
    required = {"id", "version", "provenance", "confidence", "validation_status"}
    missing = sorted(required - meta.keys())
    if missing:
        raise ValidationError(f"Persona 缺少字段 {missing}：{path}")
    if expected_id and meta["id"] != expected_id:
        raise ValidationError(f"Persona id 不匹配：{expected_id} != {meta['id']}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", meta["id"]):
        raise ValidationError(f"Persona id 无效：{meta['id']}")
    if meta["provenance"] not in PROVENANCE or meta["confidence"] not in CONFIDENCE:
        raise ValidationError(f"Persona 来源或置信度无效：{meta['id']}")
    if meta["validation_status"] not in VALIDATION_STATUS:
        raise ValidationError(f"Persona 验证状态无效：{meta['id']}")
    return meta


def load_persona_library(skill_root: Path) -> dict[str, Any]:
    path = skill_root / "references" / "personas" / "catalog.json"
    library = read_json(path)
    personas = library.get("personas")
    if library.get("schema_version") != "2.0" or not isinstance(personas, dict) or not personas:
        raise ValidationError("画像库必须是 schema_version 2.0 且包含 personas")
    required = {
        "file", "version", "name", "summary", "domains", "content_types", "platforms",
        "content_relationship", "knowledge_stage", "reading_context", "job_to_be_done",
        "pains", "trust_signals", "rejection_signals", "language_cues", "provenance",
        "confidence", "validation_status", "lifecycle",
    }
    for persona_id, entry in personas.items():
        if not isinstance(entry, dict):
            raise ValidationError(f"画像条目必须是对象：{persona_id}")
        missing = sorted(required - entry.keys())
        if missing:
            raise ValidationError(f"画像 {persona_id} 缺少字段：{missing}")
        if entry["content_relationship"] not in RELATIONSHIPS:
            raise ValidationError(f"画像关系无效：{persona_id}")
        if entry["knowledge_stage"] not in KNOWLEDGE_STAGES:
            raise ValidationError(f"画像认知阶段无效：{persona_id}")
        if entry["lifecycle"] not in LIFECYCLE:
            raise ValidationError(f"画像生命周期无效：{persona_id}")
        persona_path = path.parent / entry["file"]
        meta = validate_persona_file(persona_path, persona_id)
        for key in ("version", "provenance", "confidence", "validation_status"):
            if entry[key] != meta[key]:
                raise ValidationError(f"画像库与文件的 {key} 不一致：{persona_id}")
        for key in ("domains", "content_types", "platforms", "pains", "trust_signals", "rejection_signals", "language_cues"):
            if not isinstance(entry[key], list):
                raise ValidationError(f"画像 {persona_id} 的 {key} 必须是数组")
    return library


def load_audience_maps(skill_root: Path, library: dict[str, Any] | None = None) -> dict[str, Any]:
    library = library or load_persona_library(skill_root)
    maps = read_json(skill_root / "references" / "audience-maps.json")
    lines = maps.get("content_lines")
    if maps.get("schema_version") != "1.0" or not isinstance(lines, dict) or not lines:
        raise ValidationError("内容映射必须包含 content_lines")
    known = set(library["personas"])
    for line_id, entry in lines.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("persona_ids"), list):
            raise ValidationError(f"内容映射无效：{line_id}")
        missing = sorted(set(entry["persona_ids"]) - known)
        if missing:
            raise ValidationError(f"内容映射 {line_id} 引用了未知画像：{missing}")
    return maps


def recommend_panel(skill_root: Path, context: dict[str, Any]) -> dict[str, Any]:
    library = load_persona_library(skill_root)
    maps = load_audience_maps(skill_root, library)
    content_line = str(context.get("content_line", "")).strip()
    mapping = maps["content_lines"].get(content_line)
    if not mapping:
        return {
            "content_line": content_line,
            "candidates": [],
            "coverage": [],
            "needs_run_local_persona": True,
            "gap_reason": "没有匹配的内容线；请根据本文目标创建本次运行画像。",
        }
    platform = str(context.get("platform", "")).strip()
    candidates = []
    coverage = set()
    for persona_id in mapping["persona_ids"]:
        persona = library["personas"][persona_id]
        reasons = [f"属于内容线 {content_line}", f"提供{persona['content_relationship']}视角"]
        if platform and (platform in persona["platforms"] or "any" in persona["platforms"]):
            reasons.append(f"覆盖 {platform} 阅读场景")
        coverage.add(persona["content_relationship"])
        candidates.append({
            "id": persona_id,
            "name": persona["name"],
            "relationship": persona["content_relationship"],
            "knowledge_stage": persona["knowledge_stage"],
            "reasons": reasons,
        })
    required = set(mapping.get("required_relationships", ["core"]))
    missing = sorted(required - coverage)
    return {
        "content_line": content_line,
        "candidates": candidates,
        "coverage": sorted(coverage),
        "needs_run_local_persona": bool(missing),
        "gap_reason": f"缺少视角：{', '.join(missing)}" if missing else "",
    }


def select_personas(
    skill_root: Path,
    library: dict[str, Any],
    content_line: str | None,
    persona_ids: list[str],
    dynamic_paths: list[str],
) -> list[dict[str, Any]]:
    ids = list(persona_ids)
    if content_line:
        maps = load_audience_maps(skill_root, library)
        mapping = maps["content_lines"].get(content_line)
        if not mapping:
            raise ValidationError(f"未知内容线：{content_line}；请显式提供本次运行画像")
        ids.extend(mapping["persona_ids"])
    if len(ids) != len(set(ids)):
        raise ValidationError("评审团包含重复 Persona")
    selected = []
    base = skill_root / "references" / "personas"
    for persona_id in ids:
        entry = library["personas"].get(persona_id)
        if not entry or entry["lifecycle"] == "retired":
            raise ValidationError(f"未知或已停用的 Persona：{persona_id}")
        path = base / entry["file"]
        selected.append({"id": persona_id, "path": path, "meta": validate_persona_file(path, persona_id), "run_local": False})
    for raw in dynamic_paths:
        path = Path(raw).expanduser().resolve()
        meta = validate_persona_file(path)
        if meta["provenance"] != "synthetic" or meta["validation_status"] != "unvalidated":
            raise ValidationError("本次运行画像必须是 synthetic 且 unvalidated")
        selected.append({"id": meta["id"], "path": path, "meta": meta, "run_local": True})
    all_ids = [item["id"] for item in selected]
    if not all_ids or len(all_ids) != len(set(all_ids)):
        raise ValidationError("评审团为空或存在重复 Persona")
    return selected


def sensitive_findings(text: str) -> list[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def make_run_id(source_hash: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ur-{stamp}-{source_hash[:8]}"


def require_prepare_preview_args(args: argparse.Namespace) -> None:
    missing = [name for name in ("skill_root", "source", "goal", "output_dir") if not getattr(args, name, None)]
    if missing:
        raise ValidationError(f"prepare 预览缺少参数：{', '.join('--' + name.replace('_', '-') for name in missing)}")


def build_prepare_plan(args: argparse.Namespace) -> dict[str, Any]:
    require_prepare_preview_args(args)
    skill_root = Path(args.skill_root).resolve()
    source = Path(args.source).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not source.is_file():
        raise ValidationError(f"原文不存在：{source}")
    ensure_outside(output_dir, skill_root, "输出目录")
    source_text = read_text(source)
    if sensitive_findings(source_text):
        raise ValidationError("原文疑似包含凭证或私钥；请脱敏后再评审")
    explicit_workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None
    workspace_view = aw.load_workspace(skill_root, explicit_workspace)
    panel_id, panel_ids, _ = aw.resolve_panel(workspace_view, args.scenario)
    selected = []
    for persona_id in [*panel_ids, *args.persona]:
        if any(item["id"] == persona_id for item in selected):
            continue
        entry = workspace_view["personas"].get(persona_id)
        if not entry or entry.get("lifecycle") == "retired":
            raise ValidationError(f"未知或已停用的 Persona：{persona_id}")
        path = Path(entry["path"])
        selected.append({
            "id": persona_id,
            "path": path,
            "meta": validate_persona_file(path, persona_id),
            "run_local": False,
        })
    for raw in args.dynamic_persona:
        path = Path(raw).expanduser().resolve()
        meta = validate_persona_file(path)
        if meta["provenance"] != "synthetic" or meta["validation_status"] != "unvalidated":
            raise ValidationError("本次运行画像必须是 synthetic 且 unvalidated")
        selected.append({"id": meta["id"], "path": path, "meta": meta, "run_local": True})
    all_ids = [item["id"] for item in selected]
    if not all_ids or len(all_ids) != len(set(all_ids)):
        raise ValidationError("评审团为空或存在重复 Persona")
    source_hash = sha256_file(source)
    object_type = args.object_type
    protocol = "article-reading" if object_type == "article" else "message-testing"
    evidence_label = "validated-mainline" if object_type == "article" else "experimental-adapter"
    quorum = args.quorum if args.quorum is not None else (1 if len(selected) == 1 else max(2, math.ceil(len(selected) * 0.6)))
    if quorum < 1 or quorum > len(selected):
        raise ValidationError("quorum 必须介于 1 和 Persona 数量之间")
    run_id = args.run_id or make_run_id(source_hash)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", run_id):
        raise ValidationError("run id 无效")
    run_dir = output_dir / run_id
    panel_recommendation = aw.recommend_panel(skill_root, Path(workspace_view["workspace_path"]), panel_id)
    workspace_snapshot = {
        "manifest": workspace_view["manifest"],
        "panels": workspace_view["panels"],
        "resolved_scenario": panel_id,
        "panel_recommendation": panel_recommendation,
    }
    manifest: dict[str, Any] = {
        "schema_version": "2.0",
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "planned",
        "research_goal": args.goal,
        "source": {"name": source.name, "sha256": source_hash, "snapshot": "source-snapshot.md"},
        "selection": {
            "content_line": args.content_line,
            "scenario": panel_id,
            "explainable": True,
        },
        "stimulus": {
            "schema": "user-review-stimulus/v1",
            "object_type": object_type,
            "modality": "text",
            "protocol": protocol,
            "research_goal": args.goal,
            "exposure_context": {"scenario": panel_id},
            "source_hash": source_hash,
            "evidence_label": evidence_label,
        },
        "panel": {"planned_count": len(selected), "worker_count": len(selected), "quorum": quorum, "personas": []},
        "evidence": {"kind": "synthetic", "utility_claim": "not-evaluated"},
    }
    snapshot_bytes = (json.dumps(workspace_snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest["workspace"] = {
        "id": workspace_view["manifest"]["id"],
        "name": workspace_view["manifest"]["name"],
        "source": workspace_view["source"],
        "snapshot": "workspace-snapshot.json",
        "snapshot_sha256": sha256_bytes(snapshot_bytes),
    }
    for index, item in enumerate(selected, start=1):
        result_id = f"worker-{index:02d}-{item['id']}"
        manifest["panel"]["personas"].append({
            "id": item["id"], "version": item["meta"]["version"],
            "provenance": item["meta"]["provenance"],
            "validation_status": item["meta"]["validation_status"],
            "run_local": item["run_local"], "snapshot": f"personas/{item['id']}.md",
            "snapshot_sha256": sha256_file(item["path"]),
            "worker_result_id": result_id, "worker_result": f"workers/{result_id}.json",
            "worker_status": "queued", "attempt": 0,
        })
    inputs = {
        str(path.resolve()): sha256_file(path)
        for path in {
            source,
            Path(workspace_view["manifest_path"]),
            Path(workspace_view["panels_path"]),
            Path(workspace_view["catalog_path"]),
            *(item["path"] for item in selected),
        }
    }
    return {
        "schema": PREPARE_PLAN_SCHEMA,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "skill_root": str(skill_root),
        "output_dir": str(output_dir),
        "run_dir": str(run_dir),
        "source_path": str(source),
        "inputs": inputs,
        "manifest": manifest,
        "workspace_snapshot": workspace_snapshot,
        "personas": [
            {"id": item["id"], "path": str(item["path"]), "snapshot": f"personas/{item['id']}.md"}
            for item in selected
        ],
    }


def validate_prepare_plan_semantics(plan: dict[str, Any]) -> None:
    try:
        if plan.get("schema") != PREPARE_PLAN_SCHEMA:
            raise ValidationError("schema 无效")
        skill_root = Path(plan["skill_root"])
        if str(skill_root) != str(skill_root.resolve()) or skill_root != SCRIPT_DIR.parent.resolve():
            raise ValidationError("Skill 根目录无效")
        manifest = plan["manifest"]
        if not isinstance(manifest, dict):
            raise ValidationError("manifest 无效")
        run_id = manifest["run_id"]
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", run_id):
            raise ValidationError("run id 无效")
        output_dir = Path(plan["output_dir"])
        run_dir = Path(plan["run_dir"])
        if str(output_dir) != str(output_dir.resolve()) or str(run_dir) != str(run_dir.resolve()):
            raise ValidationError("输出路径必须是规范绝对路径")
        if run_dir != output_dir / run_id:
            raise ValidationError("run_dir 必须等于 output_dir/run_id")
        ensure_outside(output_dir, skill_root, "输出目录")

        inputs = plan["inputs"]
        if not isinstance(inputs, dict) or not inputs:
            raise ValidationError("缺少输入哈希")
        for raw, digest in inputs.items():
            if not isinstance(raw, str) or raw != str(Path(raw).resolve()):
                raise ValidationError("输入路径必须是规范绝对路径")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValidationError("输入哈希无效")

        source_path = Path(plan["source_path"])
        if str(source_path) != str(source_path.resolve()):
            raise ValidationError("原文路径必须是规范绝对路径")
        source_hash = inputs.get(str(source_path))
        source_manifest = manifest["source"]
        stimulus = manifest["stimulus"]
        if (
            not source_hash
            or source_manifest.get("sha256") != source_hash
            or source_manifest.get("snapshot") != "source-snapshot.md"
            or stimulus.get("source_hash") != source_hash
        ):
            raise ValidationError("manifest 原文哈希与计划不一致")

        workspace_snapshot = plan["workspace_snapshot"]
        workspace_manifest = manifest["workspace"]
        if not isinstance(workspace_snapshot, dict) or workspace_manifest.get("snapshot") != "workspace-snapshot.json":
            raise ValidationError("Workspace 快照契约无效")
        workspace_bytes = (json.dumps(workspace_snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if workspace_manifest.get("snapshot_sha256") != sha256_bytes(workspace_bytes):
            raise ValidationError("Workspace 快照哈希与计划不一致")

        personas = plan["personas"]
        manifest_personas = manifest["panel"]["personas"]
        if not isinstance(personas, list) or not isinstance(manifest_personas, list):
            raise ValidationError("Persona 快照列表无效")
        if len(personas) != len(manifest_personas) or manifest["panel"].get("planned_count") != len(personas):
            raise ValidationError("Persona 数量与 manifest 不一致")
        if manifest["panel"].get("worker_count") != len(personas):
            raise ValidationError("Worker 数量与 Persona 不一致")
        seen: set[str] = set()
        for item, manifest_item in zip(personas, manifest_personas):
            persona_id = item["id"]
            if not isinstance(persona_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", persona_id):
                raise ValidationError("Persona ID 无效")
            if persona_id in seen:
                raise ValidationError("Persona ID 重复")
            seen.add(persona_id)
            snapshot = f"personas/{persona_id}.md"
            if item.get("snapshot") != snapshot or manifest_item.get("snapshot") != snapshot:
                raise ValidationError("Persona snapshot 路径无效")
            persona_path = Path(item["path"])
            if str(persona_path) != str(persona_path.resolve()):
                raise ValidationError("Persona 输入路径必须是规范绝对路径")
            persona_hash = inputs.get(str(persona_path))
            if (
                manifest_item.get("id") != persona_id
                or not persona_hash
                or manifest_item.get("snapshot_sha256") != persona_hash
            ):
                raise ValidationError("Persona 快照哈希与计划不一致")
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"字段缺失或类型错误：{exc}") from exc


def apply_prepare_plan(plan: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_prepare_plan_semantics(plan)
    except ValidationError as exc:
        raise ValidationError(f"prepare 计划语义无效：{exc}") from exc
    skill_root = Path(str(plan.get("skill_root", ""))).resolve()
    run_dir = Path(str(plan.get("run_dir", ""))).resolve()
    ensure_outside(run_dir, skill_root, "输出目录")
    inputs = plan.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValidationError("prepare 计划缺少输入哈希")
    for raw, expected in inputs.items():
        path = Path(raw)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValidationError(f"prepare 输入已漂移；请重新预览：{path}")
    if run_dir.exists():
        raise ValidationError(f"运行目录已存在：{run_dir}")
    temp_dir = run_dir.with_name(f".{run_dir.name}.prepare.tmp")
    if temp_dir.exists():
        raise ValidationError(f"prepare 临时目录已存在：{temp_dir}")
    try:
        (temp_dir / "personas").mkdir(parents=True)
        (temp_dir / "workers").mkdir()
        shutil.copyfile(Path(plan["source_path"]), temp_dir / "source-snapshot.md")
        write_json(temp_dir / "workspace-snapshot.json", plan["workspace_snapshot"])
        for item in plan["personas"]:
            shutil.copyfile(Path(item["path"]), temp_dir / item["snapshot"])
        write_json(temp_dir / "manifest.json", plan["manifest"])
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir.rename(run_dir)
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
    return {"created": str(run_dir), "run_id": plan["manifest"]["run_id"]}


def prepare(args: argparse.Namespace) -> int:
    if args.apply:
        if not args.plan or not args.plan_sha256:
            raise ValidationError("prepare Apply 必须提供已预览的 --plan 和 --plan-sha256")
        plan_path = Path(args.plan).expanduser().resolve()
        if sha256_file(plan_path) != args.plan_sha256:
            raise ValidationError("prepare 计划哈希不匹配；请重新预览")
        result = apply_prepare_plan(read_json(plan_path))
        print(json.dumps(result, ensure_ascii=False))
        return 0

    plan = build_prepare_plan(args)
    preview = {"apply": bool(args.apply), "run_dir": plan["run_dir"], "manifest": plan["manifest"]}
    if args.plan:
        plan_path = Path(args.plan).expanduser().resolve()
        ensure_outside(plan_path, Path(plan["skill_root"]), "prepare 计划")
        write_json(plan_path, plan)
        preview.update({"plan": str(plan_path), "plan_sha256": sha256_file(plan_path)})
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    return 0


def persona_plan(args: argparse.Namespace) -> int:
    raise ValidationError(
        "user-review 2.0 不再向 Skill 安装目录保存画像；"
        "请创建私人 Workspace，并使用 persona-change-plan 生成变更预览。"
    )


def persona_apply(args: argparse.Namespace) -> int:
    raise ValidationError(
        "user-review 2.0 已停用旧 persona-apply；"
        "私人 Workspace 的变更必须使用 change-apply，并提交同一份预览计划的哈希。"
    )


def manifest_persona(manifest: dict[str, Any], persona_id: str) -> dict[str, Any]:
    matches = [item for item in manifest.get("panel", {}).get("personas", []) if item.get("id") == persona_id]
    if len(matches) != 1:
        raise ValidationError(f"manifest 中未唯一计划该 Persona：{persona_id}")
    return matches[0]


def planned_worker_ids(manifest: dict[str, Any]) -> set[str]:
    return {item["worker_result_id"] for item in manifest.get("panel", {}).get("personas", [])}


def iter_text(value: Any, key: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key != "quote":
                yield from iter_text(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from iter_text(child, key)
    elif isinstance(value, str):
        yield key, value


def validate_anchor(anchor: Any, source_lines: list[str], label: str) -> None:
    if not isinstance(anchor, dict):
        raise ValidationError(f"{label}.anchor 必须是对象")
    start, end, quote = anchor.get("line_start"), anchor.get("line_end"), anchor.get("quote")
    if not isinstance(start, int) or not isinstance(end, int) or not isinstance(quote, str):
        raise ValidationError(f"{label}.anchor 字段无效")
    if start < 1 or end < start or end > len(source_lines):
        raise ValidationError(f"{label}.anchor 行范围无效")
    actual = "\n".join(source_lines[start - 1:end]).strip()
    if quote.strip() not in actual:
        raise ValidationError(f"{label}.anchor 引文与原文不匹配")


def validate_worker(manifest_path: Path, result_path: Path) -> dict[str, Any]:
    manifest, result = read_json(manifest_path), read_json(result_path)
    required = {
        "schema_version", "run_id", "worker_result_id", "reviewer_kind", "source_sha256",
        "persona_id", "persona_version", "persona_provenance", "status", "coverage",
        "synthetic_signal", "confidence", "three_second_reaction", "relevance", "frictions",
        "trust_triggers", "rejection_triggers", "preserve", "questions", "next_step_reaction", "limitations",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValidationError(f"Worker 结果缺少字段：{missing}")
    if result["reviewer_kind"] != "persona":
        raise ValidationError("user-review 只接受 persona reviewer")
    if result["run_id"] != manifest["run_id"] or result["source_sha256"] != manifest["source"]["sha256"]:
        raise ValidationError("Worker 与 manifest 不匹配")
    persona = manifest_persona(manifest, result["persona_id"])
    for result_key, manifest_key in (("worker_result_id", "worker_result_id"), ("persona_version", "version"), ("persona_provenance", "provenance")):
        if result[result_key] != persona[manifest_key]:
            raise ValidationError(f"Worker 的 {result_key} 与 manifest 不匹配")
    if result["status"] != "completed" or result["synthetic_signal"] not in SIGNALS or result["confidence"] not in CONFIDENCE:
        raise ValidationError("Worker 状态、信号或置信度无效")
    source_path = manifest_path.parent / manifest["source"]["snapshot"]
    if sha256_file(source_path) != manifest["source"]["sha256"]:
        raise ValidationError("原文快照已漂移")
    source_lines = read_text(source_path).splitlines()
    for group in ("frictions", "trust_triggers", "rejection_triggers", "preserve"):
        if not isinstance(result[group], list):
            raise ValidationError(f"Worker 字段必须是数组：{group}")
        for index, item in enumerate(result[group]):
            if not isinstance(item, dict) or not isinstance(item.get("claim"), str):
                raise ValidationError(f"{group}[{index}] 缺少 claim")
            validate_anchor(item.get("anchor"), source_lines, f"{group}[{index}]")
    for key, text in iter_text(result):
        if any(pattern.search(text) for pattern in FORBIDDEN_METRIC_PATTERNS) or re.search(r"(?<!\d)\d{1,3}%", text):
            raise ValidationError(f"Worker 字段包含不支持的量化主张：{key}")
    return result


def validate_synthesis(manifest_path: Path, synthesis_path: Path) -> dict[str, Any]:
    manifest, result = read_json(manifest_path), read_json(synthesis_path)
    required = {
        "schema_version", "run_id", "source_sha256", "status", "utility_claim",
        "completed_worker_ids", "failed_worker_ids", "consensus", "divergence", "minority",
        "strategic_non_target_rejection", "preserve", "human_validation_hypotheses",
        "writing_rule_proposals", "limitations",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValidationError(f"汇总结果缺少字段：{missing}")
    if result["run_id"] != manifest["run_id"] or result["source_sha256"] != manifest["source"]["sha256"]:
        raise ValidationError("汇总结果与 manifest 不匹配")
    if result["utility_claim"] != "not-evaluated" or result["status"] not in RUN_STATUS:
        raise ValidationError("汇总状态或效用声明无效")
    planned = planned_worker_ids(manifest)
    completed, failed = set(result["completed_worker_ids"]), set(result["failed_worker_ids"])
    if completed & failed or completed | failed != planned:
        raise ValidationError("completed/failed 必须恰好划分计划 Worker")
    expected = "completed" if not failed else ("partial" if len(completed) >= manifest["panel"]["quorum"] else "failed")
    if result["status"] != expected:
        raise ValidationError(f"汇总状态必须为 {expected}")
    evidence_groups = (
        "consensus", "divergence", "minority", "strategic_non_target_rejection", "preserve",
        "human_validation_hypotheses",
    )
    for group in (*evidence_groups, "writing_rule_proposals", "limitations"):
        if not isinstance(result[group], list):
            raise ValidationError(f"汇总字段必须是数组：{group}")
    for group in evidence_groups:
        for index, item in enumerate(result[group]):
            if not isinstance(item, dict) or not isinstance(item.get("claim") or item.get("hypothesis"), str):
                raise ValidationError(f"{group}[{index}] 缺少 claim 或 hypothesis")
            refs = item.get("worker_result_ids")
            if not isinstance(refs, list) or not refs or not set(refs) <= planned:
                raise ValidationError(f"{group}[{index}] 的 worker_result_ids 无效")
    for key, text in iter_text(result):
        if any(pattern.search(text) for pattern in FORBIDDEN_METRIC_PATTERNS) or re.search(r"(?<!\d)\d{1,3}%", text):
            raise ValidationError(f"汇总字段包含不支持的量化主张：{key}")
    return result


def markdown_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        headline = value.get("claim") or value.get("hypothesis") or json.dumps(value, ensure_ascii=False)
        refs = value.get("worker_result_ids", [])
        return f"{headline}（证据：{', '.join(refs)}）" if refs else str(headline)
    return json.dumps(value, ensure_ascii=False)


def render_section(title: str, values: list[Any]) -> str:
    return f"## {title}\n\n" + ("\n".join(f"- {markdown_value(value)}" for value in values) if values else "- 无") + "\n"


def render_report(args: argparse.Namespace) -> int:
    manifest_path, synthesis_path = Path(args.manifest).resolve(), Path(args.synthesis).resolve()
    manifest = read_json(manifest_path)
    synthesis = validate_synthesis(manifest_path, synthesis_path)
    template = read_text(Path(args.template).resolve())
    output = Path(args.output).resolve()
    sections = [
        "## 证据卡\n",
        f"- 运行编号：`{manifest['run_id']}`",
        f"- 原文 SHA-256：`{manifest['source']['sha256']}`",
        f"- 完成 Worker：{len(synthesis['completed_worker_ids'])}/{manifest['panel']['worker_count']}",
        "- 证据等级：AI Persona 模拟反馈，不是真实用户访谈或行为数据\n",
        render_section("共识", synthesis["consensus"]), render_section("分歧", synthesis["divergence"]),
        render_section("少数意见", synthesis["minority"]),
        render_section("策略性非目标用户拒绝", synthesis["strategic_non_target_rejection"]),
        render_section("应该保留", synthesis["preserve"]),
        render_section("真人验证假设", synthesis["human_validation_hypotheses"]),
        render_section("局限性", synthesis["limitations"]),
        "## 原始证据索引\n", *[f"- `{worker_id}`" for worker_id in synthesis["completed_worker_ids"]],
    ]
    rendered = template.replace("{{RUN_ID}}", manifest["run_id"]).replace("{{SOURCE_SHA256}}", manifest["source"]["sha256"]).replace("{{STATUS}}", synthesis["status"]).replace("{{UTILITY_CLAIM}}", synthesis["utility_claim"]).replace("{{REPORT_BODY}}", "\n".join(sections).rstrip() + "\n")
    if output.exists() and not args.overwrite:
        raise ValidationError(f"报告已存在：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"report": str(output)}, ensure_ascii=False))
    return 0


def validate_skill(skill_root: Path) -> dict[str, Any]:
    required = [
        "SKILL.md", "LICENSE", "agents/openai.yaml", "skill.contract.yaml", "scripts/user_review.py",
        "scripts/audience_workspace.py", "references/demo-workspace/workspace.json",
        "references/demo-workspace/panels.json", "references/schemas/workspace.schema.json",
        "references/schemas/panels.schema.json", "references/schemas/change-plan.schema.json",
        "references/schemas/change-record.schema.json", "references/schemas/stimulus.schema.json",
        "references/onboarding.md", "references/architecture.md", "references/index.md",
        "references/reviewer-protocol.md", "references/persona-governance.md", "references/evidence-policy.md",
        "references/aggregation-policy.md", "references/host-adapters.md", "references/personas/catalog.json",
        "references/audience-maps.json", "references/schemas/persona.schema.json",
        "references/schemas/audience-map.schema.json", "references/schemas/run-manifest.schema.json",
        "references/schemas/worker-result.schema.json", "references/schemas/synthesis.schema.json",
        "assets/persona-template.md", "assets/worker-result-template.json", "assets/synthesis-template.json",
        "assets/report-template.md",
    ]
    missing = [item for item in required if not (skill_root / item).is_file()]
    if missing:
        raise ValidationError(f"Skill 缺少文件：{missing}")
    library = load_persona_library(skill_root)
    load_audience_maps(skill_root, library)
    text_files = [path for path in skill_root.rglob("*") if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json", ".py"}]
    forbidden = (
        "user-" + "panel-review",
        "propagation-" + "dbs",
        "method_" + "observations",
        "method_" + "findings",
        "professional_" + "reviewer",
        "professional_" + "risks",
    )
    hits = [str(path.relative_to(skill_root)) for path in text_files if any(word in read_text(path) for word in forbidden)]
    if hits:
        raise ValidationError(f"Skill 仍包含已移除的专家方法边界：{hits}")
    user_home = re.compile(r"/(?:Users|home)/[^/]+/")
    absolute_hits = [str(path.relative_to(skill_root)) for path in text_files if user_home.search(read_text(path))]
    if absolute_hits:
        raise ValidationError(f"公开包包含硬编码用户路径：{absolute_hits}")
    return {"status": "valid", "personas": len(library["personas"]), "content_lines": len(load_audience_maps(skill_root, library)["content_lines"]), "files": len(text_files)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    skill = sub.add_parser("validate-skill", help="校验 user-review Skill 包")
    skill.add_argument("--skill-root", required=True)
    listing = sub.add_parser("list-personas", help="列出长期画像库")
    listing.add_argument("--skill-root", required=True)
    recommend = sub.add_parser("recommend-panel", help="根据内容线提出可解释的评审团")
    recommend.add_argument("--skill-root", required=True)
    recommend.add_argument("--content-line", required=True)
    recommend.add_argument("--goal", required=True)
    recommend.add_argument("--platform", default="")
    prepare_parser = sub.add_parser("prepare", help="预览或创建不可变评审运行")
    prepare_parser.add_argument("--skill-root")
    prepare_parser.add_argument("--source")
    prepare_parser.add_argument("--object-type", choices=["article", "advertisement"], default="article")
    prepare_parser.add_argument("--goal")
    prepare_parser.add_argument("--output-dir")
    prepare_parser.add_argument("--content-line")
    prepare_parser.add_argument("--workspace")
    prepare_parser.add_argument("--scenario", default="default")
    prepare_parser.add_argument("--persona", action="append", default=[])
    prepare_parser.add_argument("--dynamic-persona", action="append", default=[])
    prepare_parser.add_argument("--quorum", type=int)
    prepare_parser.add_argument("--run-id")
    prepare_parser.add_argument("--plan")
    prepare_parser.add_argument("--plan-sha256")
    prepare_parser.add_argument("--apply", action="store_true")
    plan = sub.add_parser("persona-plan", help="预览保存本次运行画像")
    plan.add_argument("--persona", required=True)
    plan.add_argument("--skill-root", required=True)
    plan.add_argument("--entry", required=True, help="长期画像目录条目的 JSON 文件")
    plan.add_argument("--content-line")
    plan.add_argument("--plan", required=True)
    apply_parser = sub.add_parser("persona-apply", help="按同一不可变计划保存画像")
    apply_parser.add_argument("--plan", required=True)
    apply_parser.add_argument("--plan-sha256", required=True)
    workspace_show = sub.add_parser("workspace-show", help="查看当前 Audience Workspace")
    workspace_show.add_argument("--skill-root", required=True)
    workspace_show.add_argument("--workspace")
    workspace_show.add_argument("--data-home")
    workspace_plan = sub.add_parser("workspace-plan", help="预览创建私人 Audience Workspace")
    workspace_plan.add_argument("--skill-root", required=True)
    workspace_plan.add_argument("--seed", required=True)
    workspace_plan.add_argument("--data-home", required=True)
    workspace_plan.add_argument("--plan", required=True)
    persona_change = sub.add_parser("persona-change-plan", help="预览私人 Persona 生命周期变更")
    persona_change.add_argument("--operation", choices=["add", "update", "derive", "retire", "restore"], required=True)
    persona_change.add_argument("--skill-root", required=True)
    persona_change.add_argument("--workspace", required=True)
    persona_change.add_argument("--persona")
    persona_change.add_argument("--entry")
    persona_change.add_argument("--persona-id")
    persona_change.add_argument("--source-id")
    persona_change.add_argument("--plan", required=True)
    panel_change = sub.add_parser("panel-change-plan", help="预览默认或场景 Panel 变更")
    panel_change.add_argument("--skill-root", required=True)
    panel_change.add_argument("--workspace", required=True)
    panel_change.add_argument("--patch", required=True)
    panel_change.add_argument("--plan", required=True)
    panel_recommend = sub.add_parser("panel-recommend", help="从稳定画像中推荐可解释的场景评审团")
    panel_recommend.add_argument("--skill-root", required=True)
    panel_recommend.add_argument("--workspace")
    panel_recommend.add_argument("--scenario", default="default")
    change_apply = sub.add_parser("change-apply", help="应用同一份不可变 Workspace 变更计划")
    change_apply.add_argument("--plan", required=True)
    change_apply.add_argument("--plan-sha256", required=True)
    worker = sub.add_parser("validate-worker", help="校验 Persona Worker 结果")
    worker.add_argument("--manifest", required=True)
    worker.add_argument("--result", required=True)
    synthesis = sub.add_parser("validate-synthesis", help="校验汇总结果")
    synthesis.add_argument("--manifest", required=True)
    synthesis.add_argument("--synthesis", required=True)
    render = sub.add_parser("render-report", help="渲染 Markdown 报告")
    render.add_argument("--manifest", required=True)
    render.add_argument("--synthesis", required=True)
    render.add_argument("--template", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_cli_streams()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-skill":
            result = validate_skill(Path(args.skill_root).resolve())
        elif args.command == "list-personas":
            result = load_persona_library(Path(args.skill_root).resolve())
        elif args.command == "recommend-panel":
            result = recommend_panel(Path(args.skill_root).resolve(), {"content_line": args.content_line, "goal": args.goal, "platform": args.platform})
        elif args.command == "prepare":
            return prepare(args)
        elif args.command == "persona-plan":
            return persona_plan(args)
        elif args.command == "persona-apply":
            return persona_apply(args)
        elif args.command == "workspace-show":
            workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None
            data_home = Path(args.data_home).expanduser().resolve() if args.data_home else None
            result = aw.workspace_summary(aw.load_workspace(Path(args.skill_root).resolve(), workspace, data_home))
        elif args.command == "workspace-plan":
            result = aw.build_workspace_plan(
                Path(args.skill_root).resolve(), Path(args.data_home).expanduser().resolve(),
                Path(args.seed).expanduser().resolve(), Path(args.plan).expanduser().resolve(),
            )
        elif args.command == "persona-change-plan":
            result = aw.build_persona_plan(
                Path(args.skill_root).resolve(), Path(args.workspace).expanduser().resolve(), args.operation,
                Path(args.plan).expanduser().resolve(),
                Path(args.persona).expanduser().resolve() if args.persona else None,
                Path(args.entry).expanduser().resolve() if args.entry else None,
                args.persona_id, args.source_id,
            )
        elif args.command == "panel-change-plan":
            result = aw.build_panel_plan(
                Path(args.skill_root).resolve(), Path(args.workspace).expanduser().resolve(),
                Path(args.patch).expanduser().resolve(), Path(args.plan).expanduser().resolve(),
            )
        elif args.command == "panel-recommend":
            workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None
            result = aw.recommend_panel(Path(args.skill_root).resolve(), workspace, args.scenario)
        elif args.command == "change-apply":
            result = aw.apply_change_plan(Path(args.plan).expanduser().resolve(), args.plan_sha256)
        elif args.command == "validate-worker":
            worker = validate_worker(Path(args.manifest).resolve(), Path(args.result).resolve())
            result = {"status": "valid", "worker_result_id": worker["worker_result_id"]}
        elif args.command == "validate-synthesis":
            synthesis = validate_synthesis(Path(args.manifest).resolve(), Path(args.synthesis).resolve())
            result = {"status": "valid", "run_id": synthesis["run_id"]}
        elif args.command == "render-report":
            return render_report(args)
        else:
            raise ValidationError(f"不支持的命令：{args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, aw.WorkspaceError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
