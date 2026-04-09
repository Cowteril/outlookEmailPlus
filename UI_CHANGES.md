# UI 改动说明（工业工具化 / 去 AI 味）

本文档记录本轮前端界面“审美升级”相关改动，目标是让界面更像**大公司内部工业工具**：更强的排版秩序、更克制的颜色、更统一的组件语言；同时**不破坏任何现有功能**（接口、DOM 关键 `id`、JS 事件绑定保持不变）。

## 设计方向（本轮统一风格）

- **定位**：信息密集型管理工具 / 内部平台
- **策略**：
  - 颜色作为“信号灯”（成功/危险/强调），而不是装饰
  - 更统一的间距、边框、阴影、hover 与 focus 样式
  - 尽量减少 inline style 与“拼贴感”模块
  - 保持可读性与可访问性（键盘 focus 轮廓、长文本折行）

## 覆盖范围

### 1) 全局视觉系统

- 重建 `:root` CSS 变量体系（中性色 + 单一强调色）
- 提升标题/关键区域的排版一致性（display 字体栈 + 正文无衬线栈）
- 增加轻量背景氛围（噪点/网格/光晕，固定在 `body::before`，不影响交互）
- Fluent/Outlook 靠拢：
  - 主强调色切换为 Fluent 蓝（更接近 Outlook / Microsoft 视觉语言）
  - 控件圆角更克制（从“胶囊感”回到更接近系统控件的方圆角）

### 2) 弹窗体系（重点去“AI 拼贴感”）

将弹窗内的大量 inline 渐变块、随意阴影、零散排版，收敛为可复用的“企业级工具弹窗积木”：

- `modal-lg / modal-md / modal-sm`：统一弹窗尺寸
- `panel / panel-title / kpi-grid / action-grid / notice / scroll-panel`：统一统计块、按钮区、提示条、滚动容器
- 重做以下弹窗的视觉结构（不改功能 hook）：
  - Token 刷新管理（`#refreshModal`）
  - 错误详情（`#errorDetailModal`）
  - 获取 Refresh Token（`#getRefreshTokenModal`）

### 3) 侧边栏一致性

统一侧边栏底部与导航的颜色语言，清除残留旧暖色/国风色值：

- `user-chip / user-avatar`：更克制的材质与对比
- `GitHub / 主题 / 退出` 按钮：统一弱底色 + hover 强调
- 导航分区与条目文字色：与新 sidebar 背景一致，减少“拼贴感”
- 侧栏导航图标“成套化”：
  - 将导航项图标从 emoji 替换为统一线性 SVG（同笔画粗细/圆角/比例），避免“全灰占位符”的观感
  - 移除 `.nav-icon` 上的强制灰度滤镜，图标改为跟随 `currentColor`（默认弱灰、hover 提亮、active 更清晰）
  - 兼容侧栏收起态：图标尺寸与对齐保持一致（仅保留图标，不影响原有 `data-page`/点击逻辑）

### 4) 日志类界面统一（审计 / 刷新 / 失败列表）

新增并落地统一的日志列表组件体系（替代 inline list / onmouseover 拼贴）：

- `log-toolbar / log-surface / log-list / log-item`
- `log-title / log-sub / log-detail / log-mono`
- `badge-solid` 统一宽度与对齐，状态更稳定
- 长文本折行策略：`pre-wrap + overflow-wrap:anywhere`

涉及 JS 渲染点（保持数据结构与行为一致，仅替换输出 HTML 为 class 结构）：

- `loadRefreshLogPage()`：刷新日志页面
- `loadAuditLogPage()`：审计日志页面
- `loadFailedLogs()`：失败邮箱列表
- `loadRefreshLogs()`：弹窗中的全量刷新历史列表

## 动态文案（稳定性修复）

避免 `translateAppTextLocal(\`共 ${n} 条记录\`)` 这种“动态字符串当 key”的写法（可能导致语言包不命中或出现怪异翻译）。

改为稳定拼接：

- 中文：`共 n 条记录`
- 英文：`Total n records`

并在写入 DOM 前使用 `escapeHtml(...)`。

## Emoji 降权与微软风格文案（收口）

目标：减少“emoji + 口语化按钮文案”带来的 AI 拼贴感，让界面更像 Microsoft 工具产品（Outlook/Fluent 的短动词、克制符号）。

- **Emoji 降权策略**：
  - 文本按钮/标题：尽量移除 emoji（保留少量关键状态点）
  - icon-only 按钮：保留功能含义，但通过样式降低视觉权重（透明度、hover 反馈更克制）
  - 进度/轮询等动效符号：用更轻的符号替代（例如 `⟳`）
- **文案策略**（短动词）：
  - 例：`刷新` / `重试` / `复制` / `打开` / `导出` / `获取邮件` / `发送测试邮件`
  - 避免长句、避免 emoji 作为主信息载体

涉及文件：
- `templates/index.html`：导航/按钮/标题去 emoji、文案短动词化
- `templates/partials/modals.html`：关键按钮去 emoji（如“获取 Token”）
- `static/js/main.js`：顶栏 actions/主题按钮/轮询指示与设置页按钮回写文案收口
- `static/js/features/groups.js`：验证码按钮去 emoji，并改为更克制的次级按钮样式
- `static/js/features/temp_emails.js`：获取邮件按钮回写文案去 emoji
- `static/js/i18n.js`：补齐新增短文案的英文映射（例如“浅色模式/深色模式/导出”等）

## 深色模式（Cursor-like）

目标：深色模式不做“赛博渐变氛围”，而是更像 Cursor 一样的**中性深灰 + 少量蓝色强调 + 低饱和层级**。

变更点：
- 调整 `[data-theme="dark"]` 下的全局变量：
  - 更中性的底色与卡片层级
  - 更淡的边框与 hover，减少“发光/炫彩”
- 调整深色模式背景叠层：
  - 降低背景装饰强度，避免“AI glow”

涉及文件：
- `static/css/main.css`

## 主要改动文件

- `static/css/main.css`
  - 全局变量体系、弹窗积木、侧边栏一致性、日志组件、空态 compact、折行与 badge 对齐等
  - Fluent/Outlook-ish 按钮体系与控件圆角收敛
  - 深色模式 Cursor-like 配色与更克制的背景叠层
- `templates/partials/modals.html`
  - 关键弹窗去 inline、换成组件 class（保留原 `id` 与 onclick）
- `templates/index.html`
  - 主界面导航/标题/按钮 emoji 降权与短动词化
  - 侧栏导航图标替换为统一 SVG 套件
- `static/js/main.js`
  - `loadRefreshLogPage / loadAuditLogPage / loadFailedLogs / loadRefreshLogs`：统一输出结构与空态；修复动态翻译 key
  - 顶栏 actions / 主题按钮文案 / 轮询指示符号 / 测试按钮回写文案收口
- `static/js/i18n.js`
  - 新增短文案映射，避免动态 key 带来的翻译不命中

## 验证建议（不破坏功能）

建议手动走一遍以下路径确认功能未受影响：

- **登录页**：登录成功/失败提示正常
- **Token 刷新管理弹窗**：
  - 全量刷新 / 重试失败 / 失败邮箱 / 刷新历史展示正常
  - 刷新进度提示条显示/隐藏正常
- **刷新日志页面**（菜单：刷新日志）
  - 列表渲染、成功/失败 badge、错误信息折行正常
- **审计日志页面**（菜单：审计日志）
  - action badge、resource id、trace/ip 等信息展示正常
- **失败邮箱列表**：
  - “重试”按钮可触发原逻辑
- **主题切换**：
  - 浅色/深色按钮文案与实际主题一致；深色模式对比更接近 Cursor（更中性、少氛围光）
- **侧边栏导航**：
  - 默认/hover/active 状态下图标与文字色一致（图标不再“被强制灰化”）
  - 收起侧栏后，导航项仅显示图标且对齐/尺寸一致

## 备注

- 本轮优先做“审美与一致性”改造，**不做大规模 JS 重构**；因此 `static/js/main.js` 中部分 Sonar 风格告警属于历史遗留，未作为本轮目标。
- 若后续希望进一步提升工程质量（减少 Sonar 告警、拆分大文件、抽 UI render 函数），建议单独开一个“代码结构重构”迭代，避免与 UI 变更耦合。

