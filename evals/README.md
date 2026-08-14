# 三方评测说明

- `skill-up/`：Alibaba Skill Up 0.9.0 声明式用例。使用本机已登录的 Codex CLI 执行真实 Agent 行为；结果输出目录不得提交。
- `user-review/`：Microsoft Waza 0.38.5 兼容套件。默认 `mock` executor，只证明 schema、加载、grader 和无凭证运行链，不证明真实 Agent 行为或产品效用。
- Skill Engineering 的生产审计、不可变 improve/verify 记录保存在本地工程状态中，不进入公开 Skill 安装包。

三套结果必须分开解释：静态结构分、mock 工具链通过、真实用户模拟分别是不同证据层级。
