# 中文使用手册

## 选择 Persona 与方法

Persona 回答“谁在看”；方法包回答“按什么框架检查”。两者可以组合，但不能混为一层。

- 普通文章体验评审：只使用默认 `article-experience-core-v1`；
- 传播、共鸣、是否打中目标受众：额外启用 `propagation-dbs-v1`；
- 领域安全、事实或编辑风险：增加独立 professional reviewer，它不计入 Persona 投票。

## 推荐流程

1. 给出可读取的 Markdown 路径、研究目标和目标受众；
2. 先看 preview 中的文章哈希、Persona、方法 ID/版本和输出目录；
3. 确认后准备不可变运行目录；
4. 为每个 Persona 启动隔离 Worker；
5. 校验原文锚点、方法维度和禁止性指标；
6. 达到 quorum 后汇总；缺少 Worker 时只能标记 `partial`；
7. 渲染报告，并把需要真人验证的假设单独列出。

## 常用命令

校验安装包：

```bash
python3 skills/user-panel-review/scripts/panel_review.py validate-skill \
  --skill-root skills/user-panel-review
```

查看准备命令：

```bash
python3 skills/user-panel-review/scripts/panel_review.py prepare --help
```

校验 Worker 与汇总：

```bash
python3 skills/user-panel-review/scripts/panel_review.py validate-worker \
  --manifest /path/to/run/manifest.json \
  --result /path/to/run/workers/worker-result.json

python3 skills/user-panel-review/scripts/panel_review.py validate-synthesis \
  --manifest /path/to/run/manifest.json \
  --synthesis /path/to/run/synthesis.json
```

## 如何解读结果

- `strong / medium / weak / reject` 是合成 Persona 的序数信号；
- `effective / weak / absent` 是方法维度状态；
- `consensus` 只表示多个合成 Worker 出现相似观察；
- `minority` 不应因多数意见而被删除；
- `strategic non-target rejection` 可能说明定位清楚，不一定是文章缺陷；
- `professional_risks` 与 Persona 喜好分开；
- `human_validation_hypotheses` 才是后续真人验证入口。

## 扩展方法包

方法包注册在 `references/methods/catalog.json`。新增方法必须有唯一 ID、版本、适用对象、来源说明、维度和禁止性断言，并经过 development、holdout、negative-transfer 与人工批准。一次评审不能自动修改方法库。
