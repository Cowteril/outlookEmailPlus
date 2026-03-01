# DEVLOG（发布记录）

## v1.2.0（2026-03-01）

### 新增功能
- **UI 全局美化重设计**：从白底黑字四栏布局全面升级为现代国风设计系统（砖红 #B85C38 + 翠绿 #3A7D44 + 琥珀金 #C8963E），支持浅色/深色主题切换
- **侧边栏导航系统**：全新侧边栏支持折叠/展开，包含仪表盘、邮箱管理、临时邮箱、审计日志、刷新日志、系统设置等导航项
- **设置页面内嵌显示**：系统设置从弹窗模式改为页面内嵌直接渲染，无需额外点击
- **审计日志 & 刷新日志页面**：新增独立页面加载函数，进入即自动拉取数据
- **临时邮箱增强**：卡片新增验证码提取按钮、邮箱地址点击复制、顶栏邮箱名称可复制
- **账号头像多彩系统**：8 组渐变色按索引分配，告别单调统一颜色
- **GitHub 仓库链接**：侧边栏底部新增 GitHub 仓库快速入口
- **代码质量工具链**：新增 `pyproject.toml` 统一 black/isort 配置（line-length=127）

### 修复
- **BUG-002** 选中账号名称未在邮件栏顶部显示（`currentAccountBar` 显示逻辑修正）
- **BUG-012** 侧边栏折叠后导航图标消失（CSS 选择器排除 `.nav-icon`）
- **BUG-013** 邮箱管理页仍显示"临时邮箱"分组（`renderGroupList` 过滤）
- **BUG-014/015** 审计日志和刷新日志页面永远 loading（新增加载函数 + navigate 调用）
- **BUG-016** 设置页面从弹窗改为内嵌显示
- **BUG-018** 导入账号弹窗 textarea 尺寸优化
- **BUG-020** 临时邮箱顶栏邮箱名称不可复制
- **BUG-021** 进入邮箱管理不自动选中默认分组
- **BUG-022** 切换分组时 currentAccountBar 不重置
- **BUG-023** 收件箱/垃圾邮件 Tab 切换 active 状态不更新（`.folder-tab` → `.email-tab`）
- **BUG-024** 从临时邮箱返回邮箱管理后账号列数据残留
- **Docker CI** secrets 检测从 job-level if 改为独立 check-secrets job，修复云端构建始终跳过的问题
- **安全修复**：移除误提交的包含密钥的 `start_temp.bat`

### 重要变更
- **CI/CD 全面升级**：所有 workflow 的 `actions/checkout` 从 v4 升级至 v6
- **代码格式化**：30+ 文件 isort 导入排序修复（`--profile black`），1 文件 black 格式化
- **Dependabot 移除**：不再自动创建依赖更新 PR
- **Docker 镜像**：成功推送至 `guangshanshui/outlook-email-plus`（支持 linux/amd64 + linux/arm64）
- 新增 19 个 UI 重设计 BUG 回归测试（`test_ui_redesign_bugs.py`）

### 测试/验证
- `python -m pytest tests/ --tb=short -q`：114 个测试全部通过
- `docker build .`：本地 Docker 构建通过
- GitHub Actions：Python Tests ✅ / Code Quality ✅ / Docker Build Push ✅
- 本地服务器启动验证：`/healthz` 返回 `{"status":"ok"}`

## v1.1.1（2026-02-28）

### 新增功能
- GitHub Actions Docker 构建工作流支持推送到 Docker Hub（`guangshanshui/outlook-email-plus`），并在未配置凭据时自动跳过，避免 fork/缺失 secrets 场景构建失败。

### 修复
- README 同步更新镜像地址与仓库链接，避免用户拉取/访问到旧地址（GHCR/旧仓库）。

### 重要变更
- 容器镜像发布从 GitHub Container Registry（GHCR）切换为 Docker Hub；需要在仓库 Secrets 中配置 `DOCKERHUB_USERNAME` 与 `DOCKERHUB_TOKEN` 才会执行推送。

### 测试/验证
- `npm test`：布局系统 Jest 用例回归。
- `python -m unittest discover -s tests -v`：全量 Python 单测回归。
- `docker build .`：本地镜像构建通过（用于验证 Dockerfile 未回归）。

## v1.1.0（2026-02-27）

### 新增功能
- 新增“可调整布局系统”：支持面板拖拽调整宽度、折叠/展开指示器、布局状态持久化与版本迁移。
- 新增“恢复默认布局”入口与确认对话框，便于一键回到默认四栏布局。
- UI 导航栏展示应用版本号，便于排查问题与对齐发布版本。
- 新增布局系统测试工程（Jest）：覆盖拖拽/键盘调整、折叠/展开、状态保存/加载、窗口自适配等场景。

### 修复
- 修复窄屏下自动/手动折叠后指示器不可见、导致无法再展开的问题。
- 修复折叠后页面出现滚动条、指示器高度观感异常的问题。
- 修复“隐藏邮件列表”仅改 display 导致 Grid 仍占位的空白列问题（与布局系统联动）。

### 重要变更
- 前端布局从历史侧栏方案调整为 Grid + CSS 变量驱动的四栏式布局；折叠时通过 layout-width 变量将列宽置 0（保存宽度不丢失）。
- 新增 `layout-system-enabled` 标记类，用于与旧的窄屏侧栏样式隔离，避免样式冲突与交互回归。

### 测试/验证
- `npm test`：布局系统 Jest 覆盖单元/集成用例。
- `python -m unittest discover -s tests -v`：全量 Python 单测回归。
- 手工验证：宽屏/窄屏折叠与指示器可见性、折叠后无滚动条、重置布局可恢复默认状态。
