# Windows CLI UTF-8 回归契约

## 触发条件

- 在 Windows 或默认输出编码不是 UTF-8 的宿主上运行 `panel_review.py`。
- 将 `PYTHONIOENCODING` 设为 `ascii:backslashreplace`，模拟无法直接输出中文的控制台。

## 必须保持的行为

- `prepare` 预览成功时退出码为 `0`，标准输出是可解析的 UTF-8 JSON。
- 校验失败时退出码为 `2`，标准错误是可解析的 UTF-8 JSON。
- 中文提示必须直接输出，不得变成 `\uXXXX` 转义序列。
- 预览模式不得创建输出目录或运行工件。

## 工程回归

仓库外测试 `tests/test_user_panel_review.py` 必须在模拟非 UTF-8 默认编码时验证上述错误输出；GitHub Actions 必须覆盖 Windows、macOS 与 Linux。
