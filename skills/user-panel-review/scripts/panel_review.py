#!/usr/bin/env python3
"""用于 user-panel-review Skill 的确定性工件工具。

本模块不会启动 Agent、执行文章内容或访问网络。它会准备不可变的运行工件、
校验 Worker 证据、校验汇总结果，并根据已生成的 JSON 渲染 Markdown 报告。
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


SIGNALS = {"strong", "medium", "weak", "reject"}
CONFIDENCE = {"low", "medium", "high"}
PROVENANCE = {"grounded", "inferred", "operator_hypothesis", "synthetic"}
STATUS = {"planned", "running", "partial", "completed", "failed"}
METHOD_STATUS = {"candidate", "validated", "deprecated"}
METHOD_OBSERVATION_STATUS = {"effective", "weak", "absent"}
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
    """当产物违反公开契约时抛出。"""


def configure_cli_streams() -> None:
    """让 Windows 等宿主稳定输出未转义的中文 JSON。"""
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
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError(f"缺少 YAML frontmatter：{path}")
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"\'')
    else:
        raise ValidationError(f"YAML frontmatter 未闭合：{path}")
    return result


def validate_persona(path: Path, expected_id: str | None = None) -> dict[str, str]:
    meta = parse_frontmatter(path)
    required = {"id", "version", "niche", "provenance", "confidence", "validation_status"}
    missing = sorted(required - meta.keys())
    if missing:
        raise ValidationError(f"Persona 缺少字段 {missing}：{path}")
    if expected_id and meta["id"] != expected_id:
        raise ValidationError(f"Persona id 不匹配：预期为 {expected_id}，实际为 {meta['id']}")
    if meta["provenance"] not in PROVENANCE:
        raise ValidationError(f"不支持的 Persona provenance：{meta['provenance']}")
    if meta["confidence"] not in CONFIDENCE:
        raise ValidationError(f"不支持的 Persona confidence：{meta['confidence']}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", meta["id"]):
        raise ValidationError(f"Persona id 无效：{meta['id']}")
    return meta


def load_catalog(skill_root: Path) -> dict[str, Any]:
    catalog_path = skill_root / "references" / "personas" / "catalog.json"
    catalog = read_json(catalog_path)
    personas = catalog.get("personas")
    panels = catalog.get("panels")
    if not isinstance(personas, dict) or not isinstance(panels, dict):
        raise ValidationError("catalog 必须包含对象字段：personas、panels")
    base = catalog_path.parent
    seen_files: set[Path] = set()
    for persona_id, entry in personas.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise ValidationError(f"catalog 条目无效：{persona_id}")
        persona_path = (base / entry["file"]).resolve()
        if persona_path in seen_files:
            raise ValidationError(f"catalog 中存在重复的 Persona 文件：{entry['file']}")
        seen_files.add(persona_path)
        meta = validate_persona(persona_path, persona_id)
        for key in ("version", "niche", "provenance", "validation_status"):
            if entry.get(key) != meta.get(key):
                raise ValidationError(f"catalog/{persona_id} 的 {key} 不匹配")
    for panel_id, member_ids in panels.items():
        if not isinstance(member_ids, list) or not member_ids:
            raise ValidationError(f"panel 必须至少包含一个 Persona：{panel_id}")
        if len(member_ids) != len(set(member_ids)):
            raise ValidationError(f"panel 包含重复的 Persona ID：{panel_id}")
        missing = sorted(set(member_ids) - set(personas))
        if missing:
            raise ValidationError(f"panel {panel_id} 引用了缺失的 Persona：{missing}")
    return catalog


def load_method_catalog(skill_root: Path) -> dict[str, Any]:
    catalog_path = skill_root / "references" / "methods" / "catalog.json"
    catalog = read_json(catalog_path)
    methods = catalog.get("methods")
    if not isinstance(methods, dict) or not methods:
        raise ValidationError("方法 catalog 必须包含非空对象字段：methods")
    base = catalog_path.parent
    seen_files: set[Path] = set()
    defaults: list[str] = []
    for method_id, entry in methods.items():
        if not isinstance(entry, dict) or entry.get("id") != method_id:
            raise ValidationError(f"方法 catalog 条目 id 不匹配：{method_id}")
        required = {
            "version", "status", "object_scope", "source_type", "source_note", "default",
            "file", "dimensions", "forbidden_claims",
        }
        missing = sorted(required - entry.keys())
        if missing:
            raise ValidationError(f"方法 {method_id} 缺少字段：{missing}")
        if entry["status"] not in METHOD_STATUS or entry["object_scope"] != "article":
            raise ValidationError(f"方法 {method_id} 的状态或对象范围无效")
        if not isinstance(entry["default"], bool):
            raise ValidationError(f"方法 {method_id} 的 default 必须是布尔值")
        if entry["default"]:
            defaults.append(method_id)
        method_path = (base / entry["file"]).resolve()
        if method_path in seen_files or not method_path.is_file():
            raise ValidationError(f"方法 {method_id} 的文件缺失或重复：{entry['file']}")
        seen_files.add(method_path)
        dimensions = entry["dimensions"]
        if not isinstance(dimensions, list) or not dimensions:
            raise ValidationError(f"方法 {method_id} 必须声明维度")
        dimension_ids = [item.get("id") for item in dimensions if isinstance(item, dict)]
        if len(dimension_ids) != len(dimensions) or len(dimension_ids) != len(set(dimension_ids)):
            raise ValidationError(f"方法 {method_id} 的维度无效或重复")
        for item in dimensions:
            if not all(isinstance(item.get(key), str) and item[key] for key in ("id", "label", "theory")):
                raise ValidationError(f"方法 {method_id} 的维度字段不完整")
    if len(defaults) != 1:
        raise ValidationError("方法 catalog 必须且只能有一个默认方法")
    return catalog


def select_methods(skill_root: Path, catalog: dict[str, Any], requested_ids: list[str]) -> list[dict[str, Any]]:
    methods = catalog["methods"]
    default_ids = [method_id for method_id, entry in methods.items() if entry["default"]]
    selected_ids = default_ids + list(requested_ids)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValidationError("方法选择包含重复 ID")
    selected = []
    base = skill_root / "references" / "methods"
    for method_id in selected_ids:
        entry = methods.get(method_id)
        if entry is None:
            raise ValidationError(f"未知的方法包：{method_id}")
        selected.append({"entry": entry, "path": (base / entry["file"]).resolve()})
    return selected


def sensitive_findings(text: str) -> list[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def select_personas(
    skill_root: Path,
    catalog: dict[str, Any],
    panel: str | None,
    persona_ids: list[str],
    dynamic_paths: list[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    ids = list(persona_ids)
    if panel:
        panel_ids = catalog["panels"].get(panel)
        if panel_ids is None:
            raise ValidationError(f"未知的 panel：{panel}")
        ids.extend(panel_ids)
    if len(ids) != len(set(ids)):
        raise ValidationError("所选 panel 中包含重复的 Persona ID")
    base = skill_root / "references" / "personas"
    for persona_id in ids:
        entry = catalog["personas"].get(persona_id)
        if entry is None:
            raise ValidationError(f"未知的 Persona：{persona_id}")
        path = (base / entry["file"]).resolve()
        meta = validate_persona(path, persona_id)
        selected.append({"id": persona_id, "path": path, "meta": meta, "dynamic": False})
    for raw_path in dynamic_paths:
        path = Path(raw_path).expanduser().resolve()
        meta = validate_persona(path)
        if meta["provenance"] != "synthetic" or meta["validation_status"] != "unvalidated":
            raise ValidationError("动态 Persona 必须为 synthetic 且 unvalidated")
        selected.append({"id": meta["id"], "path": path, "meta": meta, "dynamic": True})
    all_ids = [item["id"] for item in selected]
    if not all_ids:
        raise ValidationError("panel 为空")
    if len(all_ids) != len(set(all_ids)):
        raise ValidationError("固定 Persona 与动态 Persona 中存在重复 ID")
    return selected


def make_run_id(source_hash: str) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"upr-{timestamp}-{source_hash[:8]}"


def prepare(args: argparse.Namespace) -> int:
    skill_root = Path(args.skill_root).resolve()
    source = Path(args.source).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not source.is_file():
        raise ValidationError(f"原文不存在或不是文件：{source}")
    ensure_outside(output_dir, skill_root, "输出目录")
    source_text = read_text(source)
    findings = sensitive_findings(source_text)
    if findings:
        raise ValidationError("原文疑似包含凭证或私钥；请脱敏后再评审")
    source_hash = sha256_file(source)
    catalog = load_catalog(skill_root)
    method_catalog = load_method_catalog(skill_root)
    selected_methods = select_methods(skill_root, method_catalog, args.method)
    selected = select_personas(skill_root, catalog, args.panel, args.persona, args.dynamic_persona)
    quorum = args.quorum
    if quorum is None:
        quorum = 1 if len(selected) == 1 else max(2, math.ceil(len(selected) * 0.6))
    if quorum < 1 or quorum > len(selected):
        raise ValidationError("quorum 必须介于 1 和计划 Persona 数量之间")
    run_id = args.run_id or make_run_id(source_hash)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", run_id):
        raise ValidationError("run id 无效")
    run_dir = output_dir / run_id
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "planned",
        "research_goal": args.goal,
        "source": {
            "name": source.name,
            "sha256": source_hash,
            "snapshot": "source-snapshot.md",
        },
        "panel": {
            "planned_count": len(selected),
            "quorum": quorum,
            "personas": [],
            "professional_reviewers": [],
        },
        "evidence": {
            "kind": "synthetic",
            "utility_claim": "not-evaluated",
        },
        "methods": [],
    }
    for item in selected_methods:
        entry = item["entry"]
        manifest["methods"].append(
            {
                "id": entry["id"],
                "version": entry["version"],
                "status": entry["status"],
                "file": entry["file"],
                "snapshot": f"methods/{entry['id']}.md",
                "snapshot_sha256": sha256_file(item["path"]),
                "dimensions": entry["dimensions"],
            }
        )
    for index, item in enumerate(selected, start=1):
        result_id = f"worker-{index:02d}-{item['id']}"
        manifest["panel"]["personas"].append(
            {
                "id": item["id"],
                "version": item["meta"]["version"],
                "provenance": item["meta"]["provenance"],
                "validation_status": item["meta"]["validation_status"],
                "dynamic": item["dynamic"],
                "snapshot": f"personas/{item['id']}.md",
                "snapshot_sha256": sha256_file(item["path"]),
                "worker_result_id": result_id,
                "worker_result": f"workers/{result_id}.json",
                "worker_status": "queued",
                "attempt": 0,
            }
        )
    for index, reviewer_id in enumerate(args.professional_reviewer, start=1):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", reviewer_id):
            raise ValidationError(f"专业评审者 id 无效：{reviewer_id}")
        result_id = f"professional-{index:02d}-{reviewer_id}"
        manifest["panel"]["professional_reviewers"].append(
            {
                "id": reviewer_id,
                "version": "0.1.0",
                "provenance": "synthetic",
                "counts_as_persona_vote": False,
                "worker_result_id": result_id,
                "worker_result": f"workers/{result_id}.json",
                "worker_status": "queued",
                "attempt": 0,
            }
        )
    manifest["panel"]["worker_count"] = (
        len(manifest["panel"]["personas"]) + len(manifest["panel"]["professional_reviewers"])
    )
    preview = {"apply": bool(args.apply), "run_dir": str(run_dir), "manifest": manifest}
    if not args.apply:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0
    if run_dir.exists():
        raise ValidationError(f"运行目录已存在：{run_dir}")
    (run_dir / "personas").mkdir(parents=True)
    (run_dir / "methods").mkdir()
    (run_dir / "workers").mkdir()
    shutil.copyfile(source, run_dir / "source-snapshot.md")
    for item in selected:
        shutil.copyfile(item["path"], run_dir / "personas" / f"{item['id']}.md")
    for item in selected_methods:
        shutil.copyfile(item["path"], run_dir / "methods" / f"{item['entry']['id']}.md")
    write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"created": str(run_dir), "run_id": run_id}, ensure_ascii=False))
    return 0


def manifest_persona(manifest: dict[str, Any], persona_id: str) -> dict[str, Any]:
    entries = manifest.get("panel", {}).get("personas", [])
    matches = [item for item in entries if item.get("id") == persona_id]
    if len(matches) != 1:
        raise ValidationError(f"manifest 中未唯一计划该 Persona：{persona_id}")
    return matches[0]


def manifest_professional(manifest: dict[str, Any], reviewer_id: str) -> dict[str, Any]:
    entries = manifest.get("panel", {}).get("professional_reviewers", [])
    matches = [item for item in entries if item.get("id") == reviewer_id]
    if len(matches) != 1:
        raise ValidationError(f"未唯一计划该专业评审者：{reviewer_id}")
    return matches[0]


def planned_worker_ids(manifest: dict[str, Any]) -> set[str]:
    panel = manifest.get("panel", {})
    entries = list(panel.get("personas", [])) + list(panel.get("professional_reviewers", []))
    return {item["worker_result_id"] for item in entries}


def iter_text(value: Any, key: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == "quote":
                continue
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
        raise ValidationError(f"{label}.anchor 需要整数 line_start/line_end 和字符串 quote")
    if start < 1 or end < start or end > len(source_lines):
        raise ValidationError(f"{label}.anchor 的行范围无效")
    actual = "\n".join(source_lines[start - 1 : end]).strip()
    if quote.strip() not in actual:
        raise ValidationError(f"{label}.anchor 的 quote 与原文快照不匹配")


def validate_worker(manifest_path: Path, result_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    result = read_json(result_path)
    required = {
        "schema_version", "run_id", "worker_result_id", "reviewer_kind", "source_sha256", "persona_id",
        "persona_version", "persona_provenance", "status", "coverage", "synthetic_signal",
        "confidence", "three_second_reaction", "relevance", "frictions", "preserve",
        "questions", "limitations", "method_observations",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValidationError(f"Worker 结果缺少字段：{missing}")
    if result["run_id"] != manifest.get("run_id"):
        raise ValidationError("Worker 的 run_id 与 manifest 不匹配")
    if result["source_sha256"] != manifest.get("source", {}).get("sha256"):
        raise ValidationError("Worker 的 source_sha256 与 manifest 不匹配")
    if result["reviewer_kind"] == "persona":
        persona = manifest_persona(manifest, result["persona_id"])
    elif result["reviewer_kind"] == "professional":
        persona = manifest_professional(manifest, result["persona_id"])
    else:
        raise ValidationError("reviewer_kind 必须为 persona 或 professional")
    for result_key, manifest_key in (
        ("worker_result_id", "worker_result_id"),
        ("persona_version", "version"),
        ("persona_provenance", "provenance"),
    ):
        if result[result_key] != persona[manifest_key]:
            raise ValidationError(f"Worker 的 {result_key} 与 manifest 不匹配")
    if result["status"] != "completed":
        raise ValidationError("只有 status 为 completed 的 Worker 结果可进入汇总")
    if result["synthetic_signal"] not in SIGNALS or result["confidence"] not in CONFIDENCE:
        raise ValidationError("synthetic_signal 或 confidence 无效")
    for key in ("frictions", "preserve", "questions", "limitations"):
        if not isinstance(result[key], list):
            raise ValidationError(f"Worker 字段必须是数组：{key}")
    source_path = manifest_path.parent / manifest["source"]["snapshot"]
    if sha256_file(source_path) != manifest["source"]["sha256"]:
        raise ValidationError("原文快照哈希已漂移")
    source_lines = read_text(source_path).splitlines()
    for group in ("frictions", "preserve"):
        for index, item in enumerate(result[group]):
            if not isinstance(item, dict) or not isinstance(item.get("claim"), str):
                raise ValidationError(f"{group}[{index}] 需要 claim")
            validate_anchor(item.get("anchor"), source_lines, f"{group}[{index}]")
    observations = result["method_observations"]
    if not isinstance(observations, list):
        raise ValidationError("Worker 的 method_observations 必须是数组")
    planned_dimensions: dict[tuple[str, str, str], dict[str, Any]] = {}
    for method in manifest.get("methods", []):
        snapshot_path = manifest_path.parent / method["snapshot"]
        if sha256_file(snapshot_path) != method["snapshot_sha256"]:
            raise ValidationError(f"方法快照哈希已漂移：{method['id']}")
        for dimension in method["dimensions"]:
            planned_dimensions[(method["id"], method["version"], dimension["id"])] = dimension
    seen_dimensions: set[tuple[str, str, str]] = set()
    required_observation = {
        "method_id", "method_version", "dimension_id", "dimension_label", "status", "anchor",
        "theory_basis", "observation", "evidence_level",
    }
    for index, item in enumerate(observations):
        if not isinstance(item, dict):
            raise ValidationError(f"method_observations[{index}] 必须是对象")
        missing_fields = sorted(required_observation - item.keys())
        if missing_fields:
            raise ValidationError(f"method_observations[{index}] 缺少字段：{missing_fields}")
        key = (item["method_id"], item["method_version"], item["dimension_id"])
        dimension = planned_dimensions.get(key)
        if dimension is None or key in seen_dimensions:
            raise ValidationError(f"method_observations[{index}] 未计划、版本漂移或重复")
        seen_dimensions.add(key)
        if item["dimension_label"] != dimension["label"]:
            raise ValidationError(f"method_observations[{index}] 的维度标签不匹配")
        if item["status"] not in METHOD_OBSERVATION_STATUS or item["evidence_level"] != "synthetic":
            raise ValidationError(f"method_observations[{index}] 的状态或证据等级无效")
        validate_anchor(item["anchor"], source_lines, f"method_observations[{index}]")
    if seen_dimensions != set(planned_dimensions):
        raise ValidationError("Worker 方法观察必须恰好覆盖所有已计划方法维度")
    for key, text in iter_text(result):
        if any(pattern.search(text) for pattern in FORBIDDEN_METRIC_PATTERNS):
            raise ValidationError(f"Worker 字段中包含不支持的量化指标表述：{key}")
        if re.search(r"(?<!\d)\d{1,3}%", text):
            raise ValidationError(f"Worker 字段中包含不支持的百分比主张：{key}")
    return result


def validate_synthesis(manifest_path: Path, synthesis_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    synthesis = read_json(synthesis_path)
    required = {
        "schema_version", "run_id", "source_sha256", "status", "utility_claim",
        "completed_worker_ids", "failed_worker_ids", "consensus", "divergence", "minority",
        "strategic_non_target_rejection", "preserve", "professional_risks",
        "human_validation_hypotheses", "writing_rule_proposals", "limitations", "method_findings",
    }
    missing = sorted(required - synthesis.keys())
    if missing:
        raise ValidationError(f"汇总结果缺少字段：{missing}")
    if synthesis["run_id"] != manifest.get("run_id"):
        raise ValidationError("汇总结果的 run_id 与 manifest 不匹配")
    if synthesis["source_sha256"] != manifest.get("source", {}).get("sha256"):
        raise ValidationError("汇总结果的 source_sha256 与 manifest 不匹配")
    if synthesis["status"] not in STATUS - {"planned", "running"}:
        raise ValidationError("汇总结果的 status 必须为 partial、completed 或 failed")
    if synthesis["utility_claim"] != "not-evaluated":
        raise ValidationError("v0.1 汇总结果的 utility_claim 必须保持为 not-evaluated")
    planned = planned_worker_ids(manifest)
    completed = set(synthesis["completed_worker_ids"])
    failed = set(synthesis["failed_worker_ids"])
    if completed & failed or completed | failed != planned:
        raise ValidationError("completed/failed Worker ID 必须恰好划分所有计划 Worker")
    quorum = manifest["panel"]["quorum"]
    expected_status = "completed" if not failed else ("partial" if len(completed) >= quorum else "failed")
    if synthesis["status"] != expected_status:
        raise ValidationError(f"在当前 Worker 划分下，汇总结果的 status 必须为 {expected_status}")
    for key, text in iter_text(synthesis):
        if any(pattern.search(text) for pattern in FORBIDDEN_METRIC_PATTERNS):
            raise ValidationError(f"汇总字段中包含不支持的量化指标表述：{key}")
        if re.search(r"(?<!\d)\d{1,3}%", text):
            raise ValidationError(f"汇总字段中包含不支持的百分比主张：{key}")
    allowed_ids = planned
    for group in (
        "consensus", "divergence", "minority", "strategic_non_target_rejection", "preserve",
        "professional_risks", "human_validation_hypotheses",
    ):
        if not isinstance(synthesis[group], list):
            raise ValidationError(f"汇总字段必须是数组：{group}")
        for index, item in enumerate(synthesis[group]):
            if isinstance(item, dict) and "worker_result_ids" in item:
                refs = item["worker_result_ids"]
                if not isinstance(refs, list) or not set(refs) <= allowed_ids:
                    raise ValidationError(f"{group}[{index}] 中的 worker_result_ids 无效")
    if not isinstance(synthesis["method_findings"], list):
        raise ValidationError("汇总字段必须是数组：method_findings")
    planned_dimensions: dict[tuple[str, str, str], dict[str, Any]] = {}
    for method in manifest.get("methods", []):
        for dimension in method["dimensions"]:
            planned_dimensions[(method["id"], method["version"], dimension["id"])] = dimension
    required_finding = {
        "method_id", "method_version", "dimension_id", "dimension_label", "status", "claim",
        "worker_result_ids",
    }
    for index, item in enumerate(synthesis["method_findings"]):
        if not isinstance(item, dict):
            raise ValidationError(f"method_findings[{index}] 必须是对象")
        missing_fields = sorted(required_finding - item.keys())
        if missing_fields:
            raise ValidationError(f"method_findings[{index}] 缺少字段：{missing_fields}")
        key = (item["method_id"], item["method_version"], item["dimension_id"])
        dimension = planned_dimensions.get(key)
        if dimension is None:
            raise ValidationError(f"method_findings[{index}] 引用了未计划的方法、版本或维度")
        if item["dimension_label"] != dimension["label"] or item["status"] not in METHOD_OBSERVATION_STATUS:
            raise ValidationError(f"method_findings[{index}] 的标签或状态无效")
        refs = item["worker_result_ids"]
        if not isinstance(refs, list) or not refs or not set(refs) <= allowed_ids:
            raise ValidationError(f"method_findings[{index}] 中的 worker_result_ids 无效")
    return synthesis


def markdown_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        headline = value.get("claim") or value.get("finding") or value.get("hypothesis") or json.dumps(value, ensure_ascii=False)
        refs = value.get("worker_result_ids")
        return f"{headline}（证据：{', '.join(refs)}）" if isinstance(refs, list) and refs else str(headline)
    return json.dumps(value, ensure_ascii=False)


def markdown_method_finding(value: Any) -> str:
    if not isinstance(value, dict):
        return markdown_value(value)
    method = f"{value.get('method_id')}@{value.get('method_version')}"
    dimension = value.get("dimension_label") or value.get("dimension_id")
    status = value.get("status")
    claim = value.get("claim")
    refs = value.get("worker_result_ids", [])
    evidence = f"（证据：{', '.join(refs)}）" if refs else ""
    return f"`{method}` · {dimension} · `{status}`：{claim}{evidence}"


def render_section(title: str, values: list[Any]) -> str:
    if not values:
        return f"## {title}\n\n- 无\n"
    return f"## {title}\n\n" + "\n".join(f"- {markdown_value(value)}" for value in values) + "\n"


def render_report(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    synthesis_path = Path(args.synthesis).resolve()
    manifest = read_json(manifest_path)
    synthesis = validate_synthesis(manifest_path, synthesis_path)
    template_path = Path(args.template).resolve()
    output_path = Path(args.output).resolve()
    template = read_text(template_path)
    body = [
        "## 证据卡\n",
        f"- 运行编号：`{manifest['run_id']}`",
        f"- 原文：`{manifest['source']['name']}`",
        f"- SHA-256：`{manifest['source']['sha256']}`",
        f"- 完成 Worker：{len(synthesis['completed_worker_ids'])}/{manifest['panel'].get('worker_count', manifest['panel']['planned_count'])}",
        f"- 结论状态：`{synthesis['status']}`",
        "- 证据等级：AI Persona 合成信号，不是真实用户行为数据\n",
        render_section("共识", synthesis["consensus"]),
        render_section("分歧", synthesis["divergence"]),
        render_section("少数意见", synthesis["minority"]),
        render_section("策略性非目标用户拒绝", synthesis["strategic_non_target_rejection"]),
        render_section("应该保留", synthesis["preserve"]),
        render_section("专业风险", synthesis["professional_risks"]),
        render_section("真人验证假设", synthesis["human_validation_hypotheses"]),
        "## 方法观察\n\n" + (
            "\n".join(f"- {markdown_method_finding(value)}" for value in synthesis["method_findings"])
            if synthesis["method_findings"] else "- 无"
        ) + "\n",
        render_section("局限性", synthesis["limitations"]),
        "## 原始证据索引\n",
        *[f"- `{worker_id}`" for worker_id in synthesis["completed_worker_ids"]],
    ]
    rendered = (
        template.replace("{{RUN_ID}}", manifest["run_id"])
        .replace("{{SOURCE_SHA256}}", manifest["source"]["sha256"])
        .replace("{{STATUS}}", synthesis["status"])
        .replace("{{UTILITY_CLAIM}}", synthesis["utility_claim"])
        .replace("{{REPORT_BODY}}", "\n".join(body).rstrip() + "\n")
    )
    if output_path.exists() and not args.overwrite:
        raise ValidationError(f"报告已存在；请仅在审核后使用 --overwrite：{output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(json.dumps({"report": str(output_path)}, ensure_ascii=False))
    return 0


def validate_skill(skill_root: Path) -> dict[str, Any]:
    required_files = [
        "SKILL.md", "LICENSE", "agents/openai.yaml", "skill.contract.yaml", "scripts/panel_review.py",
        "references/reviewer-protocol.md", "references/persona-governance.md",
        "references/evidence-policy.md", "references/aggregation-policy.md",
        "references/host-adapters.md", "references/personas/catalog.json",
        "references/schemas/persona.schema.json", "references/schemas/worker-result.schema.json",
        "references/schemas/run-manifest.schema.json", "references/schemas/synthesis.schema.json",
        "assets/persona-template.md", "assets/worker-result-template.json",
        "assets/synthesis-template.json", "assets/report-template.md",
        "references/methods/catalog.json", "references/methods/article-experience-core-v1.md",
        "references/methods/propagation-dbs-v1.md",
    ]
    missing = [path for path in required_files if not (skill_root / path).is_file()]
    if missing:
        raise ValidationError(f"Skill 缺少文件：{missing}")
    forbidden_dirs = [path for path in ("tests", "examples", "artifacts", "logs") if (skill_root / path).exists()]
    if forbidden_dirs:
        raise ValidationError(f"engineering/runtime 目录必须位于 Skill 包外：{forbidden_dirs}")
    load_catalog(skill_root)
    load_method_catalog(skill_root)
    for json_path in (skill_root / "assets").glob("*.json"):
        read_json(json_path)
    text_files = [path for path in skill_root.rglob("*") if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json", ".py"}]
    user_home_pattern = re.compile(r"/(?:Users|home)/[^/]+/")
    absolute_hits = [str(path.relative_to(skill_root)) for path in text_files if user_home_pattern.search(read_text(path))]
    if absolute_hits:
        raise ValidationError(f"公开包包含硬编码的用户路径：{absolute_hits}")
    return {"status": "valid", "personas": len(load_catalog(skill_root)["personas"]), "files": len(text_files)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_skill_parser = sub.add_parser("validate-skill", help="校验可部署的 Skill 包")
    validate_skill_parser.add_argument("--skill-root", required=True)

    list_parser = sub.add_parser("list-personas", help="列出已校验的稳定 Persona 和 panel")
    list_parser.add_argument("--skill-root", required=True)

    prepare_parser = sub.add_parser("prepare", help="预览或创建不可变的评审运行")
    prepare_parser.add_argument("--skill-root", required=True)
    prepare_parser.add_argument("--source", required=True)
    prepare_parser.add_argument("--goal", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--panel")
    prepare_parser.add_argument("--persona", action="append", default=[])
    prepare_parser.add_argument("--dynamic-persona", action="append", default=[])
    prepare_parser.add_argument("--professional-reviewer", action="append", default=[])
    prepare_parser.add_argument("--method", action="append", default=[])
    prepare_parser.add_argument("--quorum", type=int)
    prepare_parser.add_argument("--run-id")
    prepare_parser.add_argument("--apply", action="store_true")

    worker_parser = sub.add_parser("validate-worker", help="校验 Worker 结果及其原文锚点")
    worker_parser.add_argument("--manifest", required=True)
    worker_parser.add_argument("--result", required=True)

    synthesis_parser = sub.add_parser("validate-synthesis", help="校验汇总状态和证据引用")
    synthesis_parser.add_argument("--manifest", required=True)
    synthesis_parser.add_argument("--synthesis", required=True)

    render_parser = sub.add_parser("render-report", help="将已校验的汇总结果渲染为 Markdown")
    render_parser.add_argument("--manifest", required=True)
    render_parser.add_argument("--synthesis", required=True)
    render_parser.add_argument("--template", required=True)
    render_parser.add_argument("--output", required=True)
    render_parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_cli_streams()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-skill":
            print(json.dumps(validate_skill(Path(args.skill_root).resolve()), ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-personas":
            catalog = load_catalog(Path(args.skill_root).resolve())
            print(json.dumps(catalog, ensure_ascii=False, indent=2))
            return 0
        if args.command == "prepare":
            return prepare(args)
        if args.command == "validate-worker":
            result = validate_worker(Path(args.manifest).resolve(), Path(args.result).resolve())
            print(json.dumps({"status": "valid", "worker_result_id": result["worker_result_id"]}, ensure_ascii=False))
            return 0
        if args.command == "validate-synthesis":
            result = validate_synthesis(Path(args.manifest).resolve(), Path(args.synthesis).resolve())
            print(json.dumps({"status": "valid", "run_id": result["run_id"]}, ensure_ascii=False))
            return 0
        if args.command == "render-report":
            return render_report(args)
        raise ValidationError(f"不支持的命令：{args.command}")
    except ValidationError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
