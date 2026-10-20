# 本地记忆格式 v2（兼容 v1）

使用 Markdown 与 YAML，便于人工审阅和文本检索，不需要数据库或网络服务。

## 目录

```text
.project-finder/
├── config.yaml
├── index.md
└── memories/
    ├── implementation/
    ├── fix/
    ├── convention/
    └── decision/
```

按需创建实际使用的子目录。记录模板见 [../assets/templates/memory.md](../assets/templates/memory.md)。

v2 增加 `memories/run/`、`memories/lesson/`、`memories/workflow/`。三层为逻辑结构，不需要三套数据库。

## 配置

```yaml
schema_version: 2
projects:
  current: ..
shared_libraries: []
exclude:
  - node_modules
  - dist
  - build
  - .git
```

项目路径和共享库路径相对本知识库根目录解析，也接受用户明确配置的绝对路径。记录通过 `project` 引用配置里的项目标识，避免重复存储绝对路径。用户提供外部项目时才添加映射，不擅自猜测磁盘位置。默认排除项与目标项目已有忽略规则共同用于控制搜索范围。

共享库的来源项目映射使用该共享库自己的配置解析。读取共享库中的记录不意味着有权访问其配置指向的任意位置，仍限制在用户授权范围内。

## 记录元数据

| 字段 | 含义 |
|---|---|
| schema_version | 支持 `1`、`2`；新类型必须为 2，旧记录可保留 1 |
| id | 库内唯一、稳定的小写语义标识，如 `checkin.daily.server-vue` |
| kind | 原四种，以及 v2 的 `run` / `lesson` / `workflow` |
| title | 面向人阅读的名称 |
| status | `candidate` / `active` / `stale` / `deprecated` |
| scope | `project` 或 `cross-project`；为兼容旧格式，project 也表示非代码的工作区。后者只表明可复用范围，不授权写入共享库 |
| tags | 功能、症状、技术栈等检索词 |
| created / updated | 实际创建与修改日期 |
| sources | 来源列表；每项含 `project`、相对 `path`，可选 `symbol` 和 `revision` |
| supersedes | 被本记录替代的记录 ID 列表；同库直接使用 ID，跨库附明确库标识 |

跨库替代引用使用 `library::id`；工具只检查其格式，不跨库读取验证。记录文件放在 `memories/<kind>/`，ID 在整个本库唯一。来源 `path` 不接受绝对路径或 `..`，外部项目应通过 `projects` 映射注册。

`sources` 可以为空，例如用户明确制定的接入约定；此时必须在正文说明决定来自哪里，不能捏造代码来源。

## v2 新类型的字段

三种新类型还必须包含：

- `context`：适用条件与任务边界，非空字符串。
- `verification`：验证范围、结果与限制的简述，非空字符串，详细依据在正文。
- `related`：关联记录 ID 列表；同库 ID 或 `library::id`。它允许双向关联，不同于必须无环的 supersedes。

`run` 另含 `outcome`：`passed`、`failed`、`partial`、`unverified`。status 表示记录当前是否适用，outcome 表示任务结果；失败任务也可是一条准确有效的 active 记录。

`workflow` 另含非空字符串列表 `inputs`、`steps`、`acceptance`，分别保存输入、含分支的步骤和验收标准。正文补充输出、不适用条件及失败处理。模板见 [../assets/templates/workflow.md](../assets/templates/workflow.md) 和 [../assets/templates/run.md](../assets/templates/run.md)。

active workflow 必须 related 到本库至少一条 active 且 passed 的 run，并由该 run 的 related 指回流程，表明真实执行关联。外部证据可作线索，核实后在本库形成有来源的执行记录；不能只为通过检查伪造 run。工具只能检查关联存在，不能证明实际执行。

lesson 可使用通用模板，设 schema_version 为 2、kind 为 lesson 并加入上述三字段，正文说明条件、观察、结论和例外。

## 版本升级

新库使用配置版本 2。已有 v1 库在需要新类型并有写入授权时，保留原配置字段，仅把版本升级为 2。旧记录不必重写。v0.2 工具不支持 v2 配置，应与 Skill 一起升级；不要让新旧工具同时维护同一个库。

## 状态与证据分别表达

- `candidate`：尚不足以作为默认复用经验的发现或假设。
- `active`：有证据支持其描述范围的可用记录。用户明确制定的约定也可 active，但必须标明来源。
- `stale`：来源或适用条件存在失效迹象，需要重新核实。
- `deprecated`：明确不再推荐或已被替代。

正文逐项记录证据类型：`static`（代码检查）、`build`、`test`、`runtime`、`user-confirmed`。每项注明日期、执行内容、结果与覆盖范围。这些类型不是等级：构建成功不能证明运行正确，单次运行也不能证明所有测试情形。

非开发任务使用贴合任务的证据描述，例如数据对账、文档渲染检查、抽样核对或人工验收；不必套用代码术语。注明采用的标准和检查范围。用户没有反馈不代表验收通过。

状态不能代替验证范围。静态确认的接口约定可以 active；只做静态分析的完整业务实现通常保留 candidate。失败或未执行的检查照实记录。

## 索引

`index.md` 每条记录一行：ID、标题、类型、标签、状态、记录相对链接，可人工补充适用条件摘要。只放导航信息，详细条件与证据保存在记录中。索引可从 `memories/` 重建，人工补充内容应在重建时保留。

## 合并规则

能力、实现方式和关键适用条件一致时合并来源及证据；技术框架、接口契约或业务规则显著不同则保留独立变体并互相链接。旧验证结果保留其对应版本，不能当成新版本的测试结果。

不要求建立全局分类树。标签积累到确有导航需要时再整理，避免每次新增都更改整套分类。

## 证据与使用反馈

正文优先用以下表格记录证据，旧版文字记录仍有效：

| 日期 | 类型 | 来源版本 | 检查内容 | 结果 | 覆盖范围与限制 |
|---|---|---|---|---|---|

后续任务实际成功复用时，可以追加适配点与本次验证结果。仅仅被检索到不计为成功复用，不根据命中次数自动提升状态。

新记录的 `supersedes` 与旧记录的状态需要一致维护。维护工具会提示仍未废弃的旧记录，但不自动改动它，因为两者可能仅部分替代，应先确认适用范围。
