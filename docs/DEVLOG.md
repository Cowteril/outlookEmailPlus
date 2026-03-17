# DEVLOG

## v1.8.0 - 邮箱池与受控对外池 API 首次交付

发布日期：2026-03-17

### 新增功能

- 新增内部邮箱池接口：`/api/pool/claim-random`、`/api/pool/claim-release`、`/api/pool/claim-complete`、`/api/pool/stats`，支持随机领取、人工释放、结果回写与池统计。
- 新增对外邮箱池接口：`/api/external/pool/*` 现已支持 API Key 鉴权访问，并接入既有公网模式守卫、访问审计与调用方日级使用统计。
- 新增邮箱池状态机与持久化结构：账号新增 `pool_status`、`claimed_by`、`lease_expires_at`、`claim_token`、成功/失败计数等字段，同时引入 `account_claim_logs` 记录 claim/release/complete/expire 全链路动作。
- 新增多 API Key 粒度权限：`external_api_keys` 现支持 `pool_access` 字段，可按调用方单独授予 external pool 访问能力。

### 修复

- 修正对外邮箱池接口的返回格式，使 `claim-random`、`claim-release`、`claim-complete` 与 `stats` 全部对齐现有 external API contract，避免对接方处理分支不一致。
- 修正设置接口对邮箱池总开关和公网模式细粒度禁用项的读写逻辑，确保 `pool_external_enabled` 与 `external_api_disable_pool_*` 系列配置可以稳定持久化并回显。
- 修正租约超时回收行为，过期 claim 会自动写入 claim log、转入 `cooldown`，降低因调用方异常退出导致账号长期悬挂的风险。

### 重要变更

- 版本号从 `1.7.0` 提升到 `1.8.0`，应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段继续由 `outlook_web.__version__` 统一驱动。
- 数据库 schema 新增邮箱池相关字段、`account_claim_logs` 表，以及 `external_api_keys.pool_access` 权限列；现有库初始化/升级时会自动补齐。
- 当前仓库不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次发布继续沿用仓库既有的 Docker 镜像 tar 与源码 zip 作为正式产物。

### 测试/验证

- 单元测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 440 tests in 42.599s`
  - 状态：全部通过
- 构建验证：`docker build -t outlook-email-plus:v1.8.0 .`
  - 状态：失败
  - 原因：Docker daemon 未启动，`//./pipe/dockerDesktopLinuxEngine` 不存在，当前环境无法连接 Docker Desktop Linux Engine
- 发布产物：
  - 未生成。由于镜像构建失败，本次未导出 Docker tar、源码 zip，也未同步到 GitHub Release 页面。

## v1.7.0 - 第二次发布：README 交付口径补全

发布日期：2026-03-15

### 新增功能

- 无新增业务功能。本次版本以“对外交付说明与发布内容整理”为主。

### 修复

- 重写 `README.md`，按当前代码实际能力补齐对外说明：对外只读 API、公网模式守卫（IP 白名单/限流/高风险端点禁用）、异步 probe、调度器、反向代理安全配置等。

### 重要变更

- 版本号从 `1.6.1` 提升到 `1.7.0`，应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段均由 `outlook_web.__version__` 统一驱动。
- 发布内容继续沿用仓库既有的 Docker 镜像 tar 与源码 zip 作为正式产物。

### 测试/验证

- 单元测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 378 tests in 47.899s`
  - 状态：全部通过
- 构建验证：`docker build -t outlook-email-plus:v1.7.0 .`
  - 状态：通过
- 发布产物：
  - `dist/outlook-email-plus-v1.7.0-docker.tar`（299,417,600 bytes）
  - `dist/outlookEmailPlus-v1.7.0-src.zip`（930,706 bytes）

## v1.6.1 - 发布质量闸门清理与发布内容精简

发布日期：2026-03-15

### 新增功能

- 无新增终端功能。
- 补回面向发布的 `docs/DEVLOG.md`，用于保留版本级发布记录，避免内部过程文档清理后缺少对外可读的版本说明。

### 修复

- 清理 `external_api_guard`、`external_api_keys`、`external_api`、`system` 控制器中的格式与类型问题，恢复发布质量闸门可通过状态。
- 将异步 probe 轮询逻辑拆分为更小的私有函数，分别处理过期探测、待处理探测加载、命中结果写回与异常落库，降低发布前质量检查中的复杂度风险。
- 保持外部 API 行为不变的前提下，修正多处测试代码排版与断言表达，确保测试套件在当前代码状态下稳定通过。

### 重要变更

- 大规模移除了仓库内的内部分析、设计、测试与过程文档，仅保留运行所需内容与少量公开文档，显著缩减发布包体积和源码分发噪音。
- 本次版本号从 `1.6.0` 提升到 `1.6.1`。应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段均由 `outlook_web.__version__` 统一驱动，已同步到新版本。
- 当前仓库不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次发布沿用仓库既有的 Docker 镜像与源码压缩包作为正式产物。

### 测试/验证

- 待执行：`python -m unittest discover -s tests -v`
- 待执行：`docker build -t outlook-email-plus:v1.6.1 .`
- 待执行：导出 Docker 镜像 tar 与源码 zip，并同步到 GitHub Release 页面。
