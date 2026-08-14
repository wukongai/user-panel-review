# 贡献指南

欢迎提交问题、文档改进、公共 Persona、Panel 与刺激物适配器候选。

提交前请确保：

1. 不包含私人文章、真实凭证、绝对用户路径或运行产物；
2. 新 Persona 声明来源、版本、Segment/角色、用户任务、信任与拒绝信号；公共画像不得包含真实个人资料；
3. 新增或修改 Workspace、Persona、Panel 或适配器时补充 development、holdout 和 negative-transfer 测试；
4. 先写失败测试，再完成最小实现；
5. 运行完整 unittest 和 `validate-skill`。

一次运行产生的观察不能自动晋升为长期画像。不要提交 `~/.user-review/`、私人 Workspace、真实文章、访谈全文或运行产物。
