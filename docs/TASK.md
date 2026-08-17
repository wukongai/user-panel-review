# user-review 当前任务

## user-review 2.0：长期目标用户与模拟焦点小组

状态：Completed

完成日期：2026-08-17
远程仓库：<https://github.com/wukongai/user-review>

### 目标

把 `user-review` 交付为独立、可开源安装的目标用户反馈 Skill。普通用户只用自然语言维护长期目标用户、选择本次参与者并获得文章反馈，不需要理解内部数据结构和命令。

### 验收

- [x] 产品边界稳定为“AI 模拟目标用户焦点小组”，不包含专家评审方法；
- [x] 建立内置示例用户、我的长期目标用户、本次特殊用户三层交互；
- [x] 长期目标用户支持新增、修改、暂停、恢复和确认后安全保存；
- [x] 文章反馈默认输出共同反馈、不同意见、值得保留、最需要修改、需要真人验证；
- [x] 完成教育场景的定制、保存、文章反馈和临时用户真实连续回归；
- [x] 完成中文 README、小白手册、开发者指南、迁移说明和真实交互截图；
- [x] GitHub `main` 已更新，远程重新安装和公开用例测试通过；
- [x] 新版小白手册及 5 张截图已同步到原布丁 case；
- [x] OB 中的 Skill 交付任务、文章任务、Video Factory 伴生视频子任务和 0044 选题母舰已建立关联。

### 主要证据

- 设计：`docs/specs/2026-08-17-user-review-natural-language-ux-design.md`
- 实施计划：`docs/plans/2026-08-17-user-review-natural-language-ux-plan.md`
- 真实回归：`docs/testing/2026-08-17-user-review-natural-language-e2e.md`
- 公开转录：`docs/use-cases/user-review-first-run-transcript.json`
- 中文手册：`docs/user-guide.zh-CN.md`

### 后续边界

本任务已经关闭。未来候选只进入 `docs/BACKLOG.md`；Expert Review、Content Review 和总评审入口分别由独立任务管理，不继续追加到本任务。
