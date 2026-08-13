# 架构

## 目的

`user-panel-review` 是文章评审编排器。它将稳定协议、可叠加方法包、多个 Persona 上下文及隔离的子 Agent 运行结合起来。

```text
源快照 + 研究目标 + 方法快照
            |
       面板规划器
            |
  Persona A  Persona B  Persona C  可选专业评审者
      |          |          |                 |
 隔离的结果文件；不共享报告写入
            |
   验证 + 法定人数 + 证据检查
            |
 共识 / 分歧 / 少数观点 / 保留的优势
            |
 synthesis.json + 人类报告 + 拟议学习
```

## 职责分离

- 宿主 Agent 选择面板、启动子 Agent、重试失败并执行语义综合。
- 方法层规定“按什么框架检查”，Protocol 规定“如何执行和返回”；两者不互相替代。
- Persona worker 模拟一个视角并写入一个结果产物。
- 专业评审者评估领域风险，不计入 Persona 投票。
- 脚本执行确定性哈希、路径派生、产物验证、法定人数检查和渲染。
- 人类决定合成发现是否应影响文章或维护中的写作规则。

## 真相源

- 稳定 Persona：`references/personas/catalog.json` 及其引用的 Markdown 文件。
- 评审方法：`references/methods/catalog.json` 及其引用的版本化 Markdown 文件。
- 运行时 Persona：运行目录，绝不能放入 Skill 源代码树。
- 可复用输出布局：`assets/`。
- 评测用例和 rollout 证据：仓库级测试和文档，而不是可部署 Skill 文件夹。

## 范围

0.2 候选仍仅支持文章。产品访谈模拟、销售异议面板、落地页和课程研究在成为支持模式前，需要独立协议和证据。
