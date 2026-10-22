# 发布故障处置记录：PostgreSQL 驱动解析导致容器无法启动

- 日期：2026-10-22
- 范围：`trading-toolkit-service`（Render 生产服务）、`trading-toolkit-web`（Cloudflare Pages）
- 处置方式：无人值守排查—修复—验证，本地可复现证据全留痕
- 当前状态：已推送 main 并触发真实发布。前端发布已成功并在线验证；后端 CI 全绿、Render 发布任务见第 10 节

## 1. 结论摘要

| 项目 | 内容                                                 |
| ---- | ---------------------------------------------------- |
| 表现 | 发布后新实例反复重启，`/healthz` 健康检查持续失败    |
| 根因一 | SQLAlchemy 2.1 将 `postgresql://` 的默认 DBAPI 从 psycopg2 改为 psycopg（v3），镜像只安装 psycopg2-binary |
| 根因二 | 合并后迁移链出现两个 head，`alembic upgrade head` 直接拒绝执行（见 10.2） |
| 触发点 | 容器启动命令中的 `alembic -c /app/alembic.ini upgrade head` |
| 放大因素 | CI 全程使用 SQLite，从不执行 PostgreSQL 迁移，也从不构建/启动镜像 |
| 修复 | 连接串在进入 `create_engine` 与 Alembic 前统一补齐 `+psycopg2`；迁移链收口为单一 head；新增镜像级与迁移级 CI 门禁 |
| 附带修复 | 依赖当前系统日期的用例导致 main 长期红灯；可转债完整性校验的调用点在合并中丢失；发布任务会因缺超时而悬空 |

## 2. 时间线

| 时间 | 事件 |
| --- | --- |
| 14:15 | 接管任务，勘察双仓库结构与现有流水线 |
| 14:16 | 静态审查发现 `backend-ci.yml` 依赖安装步骤缩进异常、`setup-python` 缓存无有效依赖清单 |
| 14:20 | 以 `DATABASE_URL=postgresql://...` 运行测试，出现 `ModuleNotFoundError: No module named 'psycopg'` |
| 14:22 | 用 `alembic upgrade head --sql`（不连库）复现容器启动段的同一崩溃，确认故障点在迁移前的 engine 构造 |
| 14:24 | 关闭 `DATABASE_URL` 后跑通 174 用例，但 `test_status_refresh_only_requests_ranked_top_funds` 失败 |
| 14:30 | 定位该用例未固定 `now`，随系统日期漂移必然失败 |
| 14:40–15:20 | 实施修复，重写后端 CI 与部署工作流，重写前端 CI 与 Pages 发布工作流 |
| 15:10 | 后端 187 用例全绿；生产形态下驱动解析为 `psycopg2`，迁移生成 18 条 DDL |
| 15:20 | 前端按新流程本地验证：生产构建冒烟 + 源码级配债用例均通过 |

## 3. 根因分析

### 3.1 直接原因

托管平台注入的 `DATABASE_URL` 是不带驱动名的 `postgresql://user:pass@host:5432/db`。SQLAlchemy 2.1 起，该协议默认解析到 **psycopg（v3）** 方言：

```
File "sqlalchemy/dialects/postgresql/psycopg.py", line 497, in import_dbapi
    import psycopg
ModuleNotFoundError: No module named 'psycopg'
```

`cloudrun/requirements.txt` 只声明了 `psycopg2-binary`，因此容器内不存在 `psycopg`。崩溃发生在模块导入期（`models/database.py` 的模块级 `create_engine`），早于任何业务逻辑，也早于迁移执行。

### 3.2 为什么会"现在"才炸

`requirements.txt` 写的是 `sqlalchemy>=2.0.0`，没有上界。镜像重建时拉到 2.1.x，默认 DBAPI 语义随之改变 —— 同一份代码、同一个 Dockerfile，昨天能起、今天起不来。这属于典型的**依赖无边界 + 语义依赖库默认值**叠加故障。

### 3.3 为什么 CI 是绿的

| 缺口 | 后果 |
| --- | --- |
| 测试全程 SQLite | 永远走不到 PostgreSQL 驱动路径 |
| 从不执行 Alembic 迁移 | 容器启动的第一条命令无人验证 |
| 从不构建镜像 | Dockerfile 与镜像内依赖组合从未被验证 |
| 部署前只跑同一套 SQLite 测试 | 与 CI 等价，没有额外信息 |

于是故障只能在生产暴露，且表现为"健康检查超时"这类无信息量的现象。

### 3.4 第二个故障：时间炸弹用例

`test_status_refresh_only_requests_ranked_top_funds` 调用 `resolve_execution_rules(db, ['501001'])` 时未传 `now`，实现内 `now = now or _now()` 取系统当前时间，而断言依赖 `fund.status_checked_at.date() == today`。用例写入的检查时间是 `2026-08-10`，因此**只有 2026-08-10 当天能通过**，此后 main 分支持续红灯，等于持续冻结发布。

## 4. 修复内容

### 4.1 驱动解析（核心）

新增 `cloudrun/utils/dburl.py`，提供 `normalize_database_url` / `is_postgresql` / `describe_driver`：

- `postgresql://` → `postgresql+psycopg2://`
- `postgres://`（Render / Heroku 历史别名）→ `postgresql+psycopg2://`
- 已显式声明驱动的连接串原样保留
- SQLite 与无协议相对路径不动
- 只替换协议前缀，不解析账号密码，编码字符与查询参数原样保留

接入点：

| 文件 | 改动 |
| --- | --- |
| `cloudrun/models/database.py` | 模块级 `DATABASE_URL` 先归一化；池参数判断改用 `is_postgresql` |
| `cloudrun/migrations/env.py` | `sqlalchemy.url` 写入前归一化，保证容器启动的迁移与运行期驱动一致 |
| `cloudrun/Dockerfile` | 启动前置校验扩展为 `postgresql://` / `postgres://` / `postgresql+psycopg2://`；迁移前打印脱敏目标地址 |
| `cloudrun/app.py` | 管理健康端点不再把 PostgreSQL 报成 `mysql` |

### 4.2 回归用例

新增 `cloudrun/tests/test_database_url.py`（8 个用例），其中最关键的两个：

- `test_engine_uses_psycopg2_for_platform_url`：在子进程中以 `postgresql://` 导入 `models.database`，断言 `engine.dialect.driver == 'psycopg2'`。这条用例在修复前必然失败，直接锁定本次故障。
- `test_credentials_with_special_characters_survive`：防止归一化破坏已编码口令。

### 4.3 时间炸弹

`test_lof_execution_rules.py` 中该断言补上 `now=datetime(2026, 8, 10, 16, 0)`，与同文件其他用例的显式时间约定一致。

## 5. 验证证据

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量测试（SQLite） | `python -m pytest cloudrun/tests backtest/tests -q` | 187 passed（修复前：174 passed / 1 failed / 9 collection errors） |
| 新增回归用例 | `python -m pytest cloudrun/tests/test_database_url.py -q` | 通过 |
| 故障形态复现 | `DATABASE_URL=postgresql://... alembic upgrade head --sql` | 修复前 `ModuleNotFoundError: psycopg`；修复后生成 18 条 DDL 与 `alembic_version` 表 |
| 运行期驱动 | 子进程导入 `models.database` | `driver = psycopg2`，URL 脱敏后为 `postgresql+psycopg2://postgres:***@127.0.0.1:5432/...` |
| 前端格式门禁 | `npm run format:check:delivery` | All matched files use Prettier code style |
| 前端契约校验 | `SERVICE_CONTRACT_PATH=../trading-toolkit-service/contracts/http-api.json npm run verify:contract` | 通过 |
| 前端生产构建 | `npm run build` | 构建成功 |
| 生产构建浏览器冒烟 | `vite preview` + `verify:market-browser` / `verify:lof-market-overview` | 通过 |
| 源码级配债用例 | dev server + `verify:placement-browser` | 通过 |

## 6. 回滚与止损

### 6.1 自动回滚（已接入）

`backend-deploy.yml` 在触发部署前记录当前 `live` 部署 ID，健康检查失败时调用 Render 官方回滚接口：

```
POST https://api.render.com/v1/services/{serviceId}/rollback
Authorization: Bearer $RENDER_API_KEY
{"deployId": "<发布前的 live 部署>"}
```

回滚后继续轮询健康检查，通过则标记已恢复，失败则显式报错要求人工介入。

需要新增 Secrets：`RENDER_API_KEY`、`RENDER_SERVICE_ID`。未配置时不会静默通过，而是在 job summary 输出人工回滚步骤并失败。

### 6.2 人工回滚

1. Render Dashboard → 服务 `trading-toolkit-api` → Deploys → 选中上一个 `live` 部署 → Rollback。
2. 若本次发布已执行破坏性迁移，先确认可逆：四个迁移版本均实现了 `downgrade()`，可 `alembic downgrade -1` 逐级回退。
3. 前端回滚：`Deploy to Cloudflare Pages` 手动触发，`ref` 填入上一个可用提交 SHA，流水线会重新构建并发布，且用该构建的哈希资源名验证生效。

### 6.3 旧版本留下的坑

原流水线在 Secrets 缺失时把 `configured` 置为 `false` 并跳过发布步骤，job 依旧显示成功。现已改为显式失败 —— 否则"绿灯但没发布"会让回滚判断失去依据。

## 7. 流水线加固清单

### 构建

- 后端：CI 新增 `docker build` 与容器启动冒烟，镜像组合问题在合并前暴露。
- 后端：`python -m compileall` 语法门禁。
- 前端：`vite preview` 提供真实构建产物做浏览器冒烟，不再只测 dev server。

### 测试

- 后端：新增 `migration-smoke`（PostgreSQL 16 service 容器）——空库 `upgrade head`、断言迁移版本、断言核心表存在、以生产形态加载应用。
- 后端：新增 `container-smoke`——真实镜像 + 真实 PostgreSQL，断言 `/healthz` 信封中 `success: true` 且 `status: ok`，并断言 SQLite 配置下容器必须拒绝启动。
- 前端：浏览器验证拆为两步，生产构建冒烟与源码级用例分离，各自带上真实的就绪等待与失败日志。

### 部署

- 后端：触发时机从 `push` 改为 `workflow_run`，必须等同一提交的 Backend CI 全绿。
- 后端：`concurrency` 串行且不取消，避免两次合并的部署交错。
- 后端：健康检查预算提升到 12 分钟（48 × 15s），并校验响应信封而非仅状态码。
- 前端：弃用 `cloudflare/pages-action@v1`（固定 Wrangler 2，会忽略 `_headers`），改用 `npx wrangler@4 pages deploy`。
- 前端：生产验证从"页面里有 `/assets/`"升级为"页面引用了本次构建独有的哈希入口文件"，并额外校验该资源的 `Cache-Control: immutable`。

### 回滚与可追溯

- 两个仓库都会产出 `release-record.json`（revision、触发方式、结果、回滚目标、时间戳），上传为 90 天工件并写入 job summary。
- 前端支持按提交 SHA 手动重发，构成可执行的回滚通道。

## 8. 遗留风险

| 风险 | 说明 | 建议 |
| --- | --- | --- |
| 依赖无上界 | 本次故障本质是 `sqlalchemy>=2.0.0` 无上界 + 依赖库默认值 | 归入依赖治理：对主版本变更加人工确认，Dependabot 不自动合并 |
| Render Deploy Hook 粒度 | Hook 构建的是服务所连分支的最新提交，不是指定 SHA | 已在发布记录中留痕；如需严格对齐，改用 Render API 按 commitId 创建部署 |
| 仓库内含运行期数据库 | `cloudrun/trading_toolkit.db` 被 Git 跟踪，每次本地运行都会弄脏工作区 | 建议 `git rm --cached` 并依赖已有的 `*.db` 忽略规则（本次未执行，避免超出故障处置范围） |
| 前端契约版本 | 契约校验依赖服务端仓库，默认取 `main` | 已改为读取仓库变量 `SERVICE_CONTRACT_REF`，需要时可固定 |
| 无覆盖率门禁 | 用例数增长但无覆盖率下限 | 后续引入 `pytest-cov` 并设阈值 |

## 9. 执行边界（如实声明）

已做：

- 两个仓库均已完成本地全量回归，并推送到远端 `main`，触发真实 CI 与发布。
- 真实 PostgreSQL 上的迁移与容器启动，由新增的 `migration-smoke`、`container-smoke` 在 GitHub runner 上完成验证（结果见第 10 节）。

未做：

- **未在 WSL 中执行 `scripts/wsl/trading-toolkit deploy`**：本会话的安全策略把 `wsl.exe` 列入程序黑名单，无法从 Windows 侧进入 WSL 运行本地受管服务。本地验证改为在 Windows 侧完成等价的构建、契约、冒烟与浏览器用例；改动未引入任何 Windows 专属假设，WSL 受管交付脚本未被修改。
- **未能读取 GitHub Actions 与 Render 的运行日志**：`gh` 未登录、匿名 API 配额耗尽、Render 无 API Key，排障依赖 workflow 状态与步骤级结果，而非原始日志。

## 10. 第二轮：整合远端与真实发布

本地 `main` 落后远端（服务端落后 10 / 领先 6，前端落后 10 / 领先 1）。按要求先 `git fetch` 再安全整合，禁止强推。整合过程中又暴露出两个独立问题，均为**远端 main 既有问题**，不是本次改动引入。

### 10.1 问题三：合并把可转债完整性校验的调用点丢了

- 远端 `64c6d3b` 引入了 `services/market_data_validation.py`，但合并时两个调用边界（列表输出、快照写入）都被丢弃，模块成了死代码。
- 后果不是"测试红了"这么简单：缺转股字段的行换算出的转股价值与溢价率恒为 0，在双低排序里会被排成最优标的。对一个用于选债的工具，这是会直接影响交易判断的脏数据。
- 处置：按 `openspec/changes/validate-market-data-snapshots` 的规格恢复两个边界，并补上加载边界（历史不合格快照在重启时丢弃）。
- 同时把两个用例对齐到现行实现（它们写的是已被合并取代的分键目录设计：`get_stale` / `CACHE_SNAPSHOT_DIR` 在实现中并不存在）。

### 10.2 问题四：迁移链出现两个 head，容器必然起不来

`e1a2_lof_premium` 与 `lof_premium_observations` 都从 `d9is_placement_snapshot` 派生：

```
alembic heads → e1a2_lof_premium (head)
                lof_execution_rules_registry (head)
alembic upgrade head → Multiple head revisions are present
```

容器 CMD 固定执行 `alembic upgrade head`，因此这是**发布失败的第二条独立原因**，与驱动问题叠加。更麻烦的是两条分支创建了同名但不同列的三张表（`trading_calendar`、`lof_premium_observation`、`lof_premium_job`），即使强行升级也会撞 `table already exists`。

判定与处置：

- 以 `cloudrun/models/lof_premium.py` 为准：模型用的是 `nav_published_date` / `write_source` / `version` / `job_type` / `attempt_count`，与 `lof_premium_observations` 一致；`e1a2` 的 `nav_date` / `captured_by` / `job_key` 是被取代的草稿。
- `e1a2_lof_premium` 保留修订号（兼容已打标的数据库，避免 `Can't locate revision`），改为空修订。
- 新增 `m1022_merge_lof_heads` 合并修订收口为单一 head。
- 新增 `tests/test_migrations.py`：head 必须唯一、不得有孤立修订、不得重复建表。

### 10.3 问题五：发布任务会悬空

首次真实发布时，`Backend Deploy to Render` 运行 20 分钟仍未收敛。原因是健康检查按「次数 × 间隔」计预算，而每轮 curl 自身可占满 `--max-time`，最坏耗时远超注释声称的 12 分钟；同时 Render API 的若干 curl 完全没有超时，网络挂起会把任务挂到 GitHub 默认的 6 小时上限。

处置：改为墙钟 deadline（20 分钟）、单次 curl 有界收缩、所有外部调用补 `--connect-timeout` / `--max-time`、给 job 加 `timeout-minutes: 35`。12 个工作流片段全部通过 `bash -n`。

### 10.4 真实发布结果

| 项目 | 结果 |
| --- | --- |
| 服务端 `b89f5cf` Backend CI | **success**：单元测试、PostgreSQL 迁移冒烟、镜像启动冒烟三个 job 全绿 |
| 服务端 `d63f94d` Backend CI | failure（首次推送，暴露双 head 问题），部署被正确拦下、未发布 |
| 前端 `750f781` CI | **success** |
| 前端 `750f781` Deploy to Cloudflare Pages | **success** |
| 前端生产站点 | 已切换：`/assets/index-UKLh1Axn.js`，`Cache-Control: public, max-age=31536000, immutable` |

前端从 CI 到生产验证整条链路走通，说明新的 `wrangler@4` 发布方式与"哈希入口 + immutable"校验在真实环境可用。

后端 `Backend Deploy to Render` 在本记录写作时仍未收敛（见 10.3），其状态需在 GitHub Actions 页面确认；若因网络不可达判定失败，流水线会走人工回滚路径并在 job summary 给出手工步骤。
