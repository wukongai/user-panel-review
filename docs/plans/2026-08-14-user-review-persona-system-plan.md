# user-review 0.3.0 实施计划

对应规格：`docs/specs/2026-08-14-user-review-persona-system-design.md`

## 不可变实施范围

本计划只把现有仓库重构为 `user-review`。不创建 `expert-review` 或 `article-review`，不迁移任何专家方法。

## 阶段 1：建立失败基线

- 为新 Skill 名称、三层画像模型、临时画像不落库和显式保存添加失败测试；
- 为“不得出现专家方法字段”添加负向回归；
- 保留隔离 Worker、源哈希、法定人数和部分失败测试。

## 阶段 2：身份与目录迁移

- 将 `skills/user-panel-review` 改为 `skills/user-review`；
- 将脚本改名为 `user_review.py`，统一 Skill 元数据、contract、schema ID 和示例；
- 将测试目录与测试模块改为 `user-review` / `test_user_review.py`；
- 不保留第二个可发现的旧 Skill 入口。

## 阶段 3：删除错误职责

- 删除方法目录、DBS 方法、专业评审者参数和数据结构；
- 从 Worker、manifest、synthesis schema 与渲染器中删除方法和专业风险字段；
- 将评审协议恢复为纯 Persona 阅读反馈与证据锚定。

## 阶段 4：实现画像系统

- 增加长期画像目录、内容映射目录和对应 schema；
- 增加画像库与内容映射的 validate/list/preview/apply 操作；
- 增加按文章元数据提出候选评审团、说明入选原因和发现覆盖缺口的确定性能力；
- 增加运行级临时画像，并确保默认不写入长期画像库；
- 显式保存时要求引用同一预览计划并检查漂移；
- `prepare` 固化文章和 Persona 快照。

## 阶段 5：文档与版本

- 重写中文 README，突出焦点小组、画像管理与使用边界；
- 重写中文用户手册并增加旧名称迁移章节；
- 更新 Changelog、版本与发布检查；
- 删除独立“方法论说明”，或改为只说明模拟焦点小组证据边界。

## 阶段 6：验证与发布

- 运行单元测试、Skill validation、凭证扫描和 `git diff --check`；
- 在干净临时目录从本地候选执行安装和完整文章评审；
- 用户确认本地结果后提交；
- 单独执行 GitHub 仓库改名，更新远程地址并推送；
- 从 `wukongai/user-review` 重新安装并完成远程回归；
- 本轮不打 tag、不创建 Release，除非用户另行明确授权。

## 回滚

- 实施前保留当前 Git 提交与未提交文档差异；
- 代码改动只发生在独立公开仓库工作副本；
- GitHub 改名最后执行；如远程回归失败，先修复同一候选，不发布不完整状态；
- 不删除用户正式源仓库中的任何未提交文件。

