# User Review 2.0：长期用户画像与模拟焦点小组设计

状态：已确认，进入实施  
日期：2026-08-15  
目标版本：2.0.0  

## 1. 产品定义

`user-review` 是一个独立、可开源安装的长期用户画像与模拟焦点小组产品。它帮助一个自媒体 IP、企业或相对独立的产品线维护一套相对稳定的目标用户画像，并在不同内容场景中复用这些画像，模拟目标用户的理解、感受、信任、异议和下一步意愿。

稳定不变量是“模拟目标受众焦点小组”，不是文章评审，也不是专业方法评审。文章是已经完成真实回归的第一个刺激物适配器。

产品必须让普通用户完成以下闭环，而不要求创建 Content Factory、不要求复制 Skill，也不要求手工编辑 JSON：

1. 安装后立即用示范 IP 和公共画像完成第一次评审；
2. 通过对话把示范 IP 改成自己的受众空间；
3. 持续新增、修改、派生、停用和恢复长期画像；
4. 维护默认评审团和针对不同业务场景的评审团；
5. 对任意一次评审预览画像选择，允许增删或加入临时画像；
6. 保存可追溯的评审结果和画像优化建议，但不自动污染长期画像；
7. 升级或重装 Skill 后，私人画像仍然存在。

## 2. 已验证需求来源

本设计吸收以下已确认输入：

- 0.3.0 已验证的 Persona 快照、隔离 Worker、法定人数、部分失败、原文锚点和模拟证据边界；
- 《用户调研必看：一个 AI 用户评审 Skill 怎么搭》中“赛道级画像长期复用、单篇特殊画像临时增加”的产品承诺；
- 2026-08-15 Handoff 中“目标受众可直接体验的 Stimulus Package”长期边界；
- 用户明确要求 `user-review` 独立于 Content Factory，并像 IP 配图一样提供示范配置和改成自己的引导；
- 当前实现只完整支持新增画像，尚不完整支持已有画像修改、停用、恢复和独立映射治理的失败证据。

## 3. 核心概念

### 3.1 Audience Workspace

一个 Audience Workspace 代表一个相对稳定的受众系统，通常对应：

- 一个自媒体 IP；
- 一个企业品牌；
- 一个产品线；
- 一个目标用户显著独立的业务。

同一企业如果存在完全不同的产品线，应创建多个 Workspace，而不是把所有客户塞进一个画像库。

Workspace 至少包含：

```text
Audience Workspace
├── workspace.json            # 业务、受众承诺、默认场景和 schema 版本
├── personas/
│   ├── catalog.json          # 私人长期画像目录
│   └── *.md                  # 私人画像正文
├── panels.json               # 默认评审团和场景评审团
├── change-plans/             # 待确认的不可变变更计划
├── change-records/           # 已应用变更与撤销依据
├── backups/                  # 受控变更前备份
└── learning/                 # 评审产生的画像优化建议，不自动应用
```

### 3.2 Persona、Segment 与 Panel

- Segment 回答“有哪几群真实不同的人”；
- Persona 把一群人的共同任务、处境、痛点、信任和拒绝信号写成可进入评审席的角色；
- Panel 回答“这一次让哪些 Persona 参加”。

Persona 不按文章、销售页或落地页复制。内容格式变化不等于用户变化。

只有以下情况才建议新建长期 Persona：

- 使用者、购买者和批准者是不同角色；
- 用户任务、成熟阶段、痛点或拒绝条件有实质差异；
- 新产品线服务另一批目标用户；
- 多次评审或真实研究证明现有分层过粗。

以下情况只调整 Panel 或本次上下文，不新建长期 Persona：

- 同一用户从文章进入销售页；
- 只改变文章主题、平台或格式；
- 同一用户面对不同内容产生不同反应；
- 只是需要一个一次性的挑战视角。

### 3.3 默认评审团与场景评审团

每个 Workspace 必须有一个默认评审团，供多数日常内容使用。场景评审团只保存对默认组合的可解释调整，不复制 Persona。

场景优先描述用户所处的业务阶段，而不是文件格式：

- `education`：认知、教育和内容理解；
- `consideration`：比较方案、建立信任和处理异议；
- `decision`：购买、采用或批准决策；
- `onboarding`：开始使用和理解下一步。

用户可以自定义场景名称。推荐结果必须说明每个 Persona 为什么进入，不展示不可解释的神秘总分。

## 4. 三层数据模型

### 4.1 公共内置层

公共仓库内置：

- 一套可直接运行的虚构示范 IP；
- 通用 Persona 与默认/场景 Panel；
- 画像模板、schema、引导问题和示例评审；
- 不包含作者真实私人画像、访谈原文、凭证或内部业务配置。

内置层只读并随 Skill 升级。修改内置 Persona 时，系统必须在私人层创建派生画像，使用新 ID 并记录 `derived_from`，不得覆盖内置文件。

### 4.2 私人长期层

私人画像由 `user-review` 自己管理，默认位于：

```text
~/.user-review/workspaces/<workspace-id>/
```

路径解析优先级：

1. 命令显式指定的 `--workspace`；
2. `USER_REVIEW_WORKSPACE` 指向的路径；
3. 当前激活的用户级 Workspace；
4. 只读示范 Workspace。

私人数据不位于 Skill 安装目录，因此更新、卸载或重新安装不会覆盖。公开仓库不得扫描、打包或上传该目录。

### 4.3 单次运行层

单次临时 Persona 只进入当前 Run Panel 和不可变快照。默认不写入长期库。用户明确要求保存时，也必须重新进入 Persona 变更计划，不得从运行目录静默晋升。

## 5. Persona 数据契约

长期 Persona 至少包含：

- `id`、`version`、`name`、`summary`；
- `segment`、`role`、`content_relationship`；
- `knowledge_stage`、`reading_context`；
- `job_to_be_done`、`pains`、`constraints`；
- `trust_signals`、`rejection_signals`、`language_cues`；
- `provenance`、`confidence`、`validation_status`；
- `lifecycle`、`derived_from`、`created_at`、`updated_at`。

人口属性只有在用户主动提供、任务确有必要且不会造成敏感推断时才可记录。不得推断健康、政治、宗教、民族、性取向等敏感身份。

生命周期：

- `candidate`：尚未确认进入默认推荐；
- `reusable`：可进入长期 Panel；
- `retired`：保留历史但不得进入新运行。

来源：

- `grounded`：来自脱敏研究或业务证据；
- `inferred`：从已有材料谨慎推断；
- `operator_hypothesis`：操作者工作假设；
- `synthetic`：为一次模拟创建。

AI 根据对话生成的初始私人画像默认是 `operator_hypothesis`、`low`、`unvalidated`；不得因文本逼真自动升级可信度。

## 6. 画像创建与维护体验

### 6.1 第一次使用

提供两个入口：

1. `体验示范 IP`：不创建私人数据，直接使用内置 Workspace；
2. `创建我的用户空间`：通过一次一个问题的对话生成候选 Workspace。

创建引导最多围绕五类信息：

1. 提供什么内容、产品或服务；
2. 主要帮助谁完成什么任务；
3. 用户处于哪些不同阶段；
4. 谁是使用者、购买者和批准者；
5. 什么建立信任，什么导致拒绝。

系统生成 3～5 个差异明确的初始 Persona、一个默认 Panel 和必要的场景 Panel 建议。预览必须展示分层依据、Persona 差异、来源和未知项；用户确认同一计划后才创建 Workspace。

### 6.2 变更操作

2.0 必须正式支持：

- `add`：新增私人 Persona；
- `update`：修改已有私人 Persona，并强制版本递增；
- `derive`：从内置或私人 Persona 派生新 Persona，使用新 ID；
- `retire`：停用但不删除；
- `restore`：从 retired 恢复为 candidate 或 reusable；
- `panel-update`：新增、修改或移除默认/场景 Panel 中的引用。

不在 2.0 自动实现 Persona 合并和硬删除。合并需要身份、历史引用和证据迁移设计；硬删除会破坏历史可追溯性。

### 6.3 Preview / Apply 事务

所有长期变更必须：

1. 生成不可变计划；
2. 展示字段差异、版本变化、受影响 Panel 和文件路径；
3. 校验 Persona、目录和 Panel 的变更前哈希；
4. 用户确认同一计划哈希后应用；
5. 写入前备份，采用临时文件加原子替换；
6. 任一文件失败则恢复全部变更；
7. 生成 Change Record，记录撤销所需的文件指纹；
8. 历史 Run Snapshot 永不改变。

## 7. 内容匹配与用户模拟

### 7.1 画像相对稳定，反应动态生成

每位 Worker 的输入由四部分组成：

```text
稳定 Persona 快照
  + 目标受众实际看到的 Stimulus Snapshot
  + Exposure Context
  + Research Goal / Protocol
```

同一 Persona 面对不同内容可以产生不同反应，但反应只进入运行结果，不直接写回长期 Persona。

### 7.2 自动选团

选团顺序：

1. 解析显式 Workspace 和场景；
2. 读取默认 Panel；
3. 应用场景 Panel 的新增/移除；
4. 排除 retired Persona；
5. 检查核心、邻近、挑战视角以及使用者/购买者/批准者是否按任务需要覆盖；
6. 报告缺口并建议本次临时 Persona；
7. 展示候选、来源、入选原因和缺口，允许用户调整；
8. 确认后固化快照。

内容类型只是上下文之一，不能成为复制 Persona 的理由。场景和研究目标比文件扩展名优先。

### 7.3 模拟输出

每个 Persona 输出：

- 第一印象；
- 理解与误解；
- 相关性；
- 情绪与感受；
- 信任点和怀疑点；
- 主要异议；
- 希望补充的证据；
- 可能采取或拒绝采取的下一步；
- 应保留内容；
- 刺激物证据锚点；
- 限制和不确定性。

汇总继续保留共识、分歧、少数意见、战略性非目标拒绝、法定人数、部分失败和真人验证假设，不进行人数比例或效果预测。

## 8. Stimulus Package 与适配器边界

长期输入边界接受 Handoff 定义：目标受众能够直接看到、听到或以非交互方式体验的刺激物。

内部接口采用版本化 Stimulus Package：

```yaml
schema: user-review-stimulus/v1
object_type: article
modality: text
exposure_context: {}
target_audience: ""
research_goal: ""
content_elements: []
evidence_anchors: []
internal_context_excluded: []
source_hash: ""
```

2.0 的发布主线仍是文章。第二适配器只作为画像底座完成后的架构验证，选择 `advertisement` 的纯文本刺激物和 `message-testing` 协议。它不得阻塞画像系统和文章开源交付；没有完成真实回归前不得出现在主要能力声明中。

落地页、产品概念、课程、视频和混合媒体保持非目标。交互式原型必须交给独立可用性测试，不能伪装成焦点小组。

## 9. 明确非目标

本版本不创建、复制或修改：

- `expert-review`、`content-expert-review` 或 `content-review`；
- `professional_reviewer`、`method_observations`、`theory_basis`；
- DBS、传播学量表或其他专家方法包；
- PRD、代码、架构、合规或平台规则评审；
- 交互式可用性测试；
- 真实访谈、真实焦点小组、CTR、转化、ROAS 或学习效果预测；
- Content Factory 专属配置或运行依赖。

## 10. 开源仓库与隐私边界

`wukongai/user-review` 是唯一代码事实源。公开仓库包含引擎、schema、示范 IP、测试和手册；任何调用项目只是消费者。

公开仓库必须：

- 使用虚构示范 IP，不使用作者真实私人画像；
- 不读取 `.env`、Cookie、Token、SSH、浏览器状态或完整会话；
- 不收集原始访谈全文，默认只记录脱敏来源摘要；
- 不扫描或打包 `~/.user-review/`；
- 安装、更新和卸载说明明确私人数据不会随 Skill 删除；
- 提供导出、备份和恢复路径，但不自动上传云端。

## 11. 用户手册

中文手册独立于自媒体文章，承担从引流到成功使用的落地任务。必须覆盖：

1. 一分钟安装；
2. 用示范 IP 完成第一次文章评审；
3. 创建自己的 Audience Workspace；
4. 理解用户分层、Persona、默认 Panel 和场景 Panel；
5. 新增、修改、派生、停用和恢复 Persona；
6. 为文章选择默认或针对性 Panel；
7. 临时 Persona 保存到长期库的确认流程；
8. 更新、卸载、备份、恢复和跨机器迁移；
9. 模拟反馈、隐私和真实研究边界；
10. 常见失败及唯一下一步。

现有手册中“叠加方法包”“创建项目级 Skill 副本”和修改已安装目录的内容必须删除。用户定制的是自己的数据，不是 fork 一份 Skill。

## 12. 兼容与迁移

2.0 是破坏性数据边界升级：

- 0.3 内置 Persona 继续作为只读公共资产；
- 0.3 文章运行、Worker、汇总与报告结构保持兼容；
- 旧 `persona-plan` / `persona-apply` 不再向 Skill 源目录写入，迁移为 Workspace 事务或提供明确弃用错误；
- 如果用户曾修改安装目录，提供导入到私人 Workspace 的预览，不自动覆盖；
- 公开版本、README、Changelog、contract、schema 和测试必须一致；
- 不声称未完成真实回归的适配器可用。

## 13. 验收标准

### 13.1 产品与数据

1. 干净安装后不创建私人数据也能使用示范 IP；
2. 用户能通过预览/确认创建独立 Workspace；
3. 私人 Workspace 不在 Skill 安装目录，更新后仍可读取；
4. 公共和私人 Persona 可合并解析，ID 冲突被拒绝；
5. 内置 Persona 只能派生，不能覆盖；
6. Persona add/update/derive/retire/restore 全部有版本、影响预览、备份、记录和漂移保护；
7. 默认 Panel 与场景 Panel 可受控修改；
8. 单次临时 Persona 默认不落库；
9. 历史 Run Snapshot 不受长期画像后续修改影响。

### 13.2 焦点小组与边界

10. 文章评审的隔离 Worker、法定人数、部分失败、证据锚点和报告继续通过；
11. 同一 Persona 可在不同场景中产生动态反应而不复制长期画像；
12. 专家方法字段、DBS、真实效果预测和交互可用性声明不存在；
13. 第二适配器没有真实回归前不进入主要能力声明。

### 13.3 开源与工程

14. README、中文手册、示范 IP、迁移说明和 CLI 帮助一致；
15. Python 标准库运行，不新增运行时依赖；
16. pytest/unittest、Ruff、Agent Skill validation、credential lint 和 diff check 通过；
17. Skill Engineering production audit 通过，结构分与真实效用证据分开报告；
18. Alibaba Skill Up 至少覆盖触发、画像维护、负向边界和文章回归；
19. Microsoft Waza 在无凭证可执行边界内完成 config/check 或 mock 验证；真实 runner 未运行时明确记录限制；
20. 从远程仓库干净安装后，完成“示范 IP → 创建私人 Workspace → 修改画像 → 评审真实文章 → 确认数据仍在”的完整用户模拟；
21. 未提交私人画像、真实文章、凭证、临时运行目录或完整会话。

