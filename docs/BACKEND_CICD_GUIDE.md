# 后端 CI/CD 部署指南（GitHub Actions + 腾讯云 CloudBase）

## 架构概览

```
代码推送 → GitHub Actions CI（测试）→ GitHub Actions CD（部署）→ CloudBase 云托管
                ↓                           ↓
          跑测试脚本                  Docker 构建并部署
```

- **CI（持续集成）**：GitHub Actions 自动安装依赖 + 跑测试
- **CD（持续部署）**：GitHub Actions 用 CloudBase CLI 部署到云托管
- **免费额度**：CloudBase 新用户有免费额度（以[官方文档](https://cloud.tencent.com/document/product/876/47818)为准），GitHub Actions 公开仓库免费

---

## 第一步：在 GitHub 创建后端仓库

### 1.1 创建新仓库

1. 访问 https://github.com/new
2. 填写信息：
   - Repository name: `trading-toolkit`
   - Description: `旺财百宝箱后端 - Flask API`
   - 选择 **Public**（公开，GitHub Actions 无限免费）
   - **不要**勾选 "Add a README file"
   - **不要**勾选 ".gitignore"（已有）
3. 点击 **Create repository**

### 1.2 添加 GitHub remote 并推送

在后端仓库目录执行：

```bash
cd d:\Develop\GitHub\trading-toolkit

# 查看当前 remote（确认是否已配置 GitHub remote）
git remote -v

# 如果没有 github remote，添加（替换 amostodo 为你的用户名）
git remote add github https://github.com/amostodo/trading-toolkit.git

# 推送到 GitHub
git push github main
```

如果提示仓库不存在，先确认在 GitHub 上创建了 `trading-toolkit` 仓库。

### 1.3 验证推送成功

访问 `https://github.com/amostodo/trading-toolkit`，应该能看到代码。

---

## 第二步：开通腾讯云 CloudBase

### 2.1 注册腾讯云账号

1. 访问 https://cloud.tencent.com/
2. 点击右上角"注册"，完成实名认证

### 2.2 开通 CloudBase（云开发）

1. 访问 https://console.cloud.tencent.com/tcb
2. 点击"立即开通"
3. 创建环境：
   - 环境名称：`trading-toolkit`（自定义）
   - 套餐：选择**按量付费**（有免费额度，不会扣费）
4. 记录**环境 ID**（形如 `trading-toolkit-xxxxx`）

### 2.3 开通云托管

1. 在 CloudBase 控制台左侧菜单 → **云托管** → **服务列表**
2. 点击**新建服务**：
   - 服务名称：`trading-toolkit-api`
   - 记录**服务 ID**
3. 创建后进入服务 → **服务设置** → 确认端口为 `8080`

> **注意**：云托管容器是临时性的，重启后数据会丢失。生产环境建议将数据库迁移到腾讯云 MySQL/MariaDB 或使用云数据库，而非容器内的 SQLite。

### 2.4 获取 API 密钥

1. 访问 https://console.cloud.tencent.com/cam/capi
2. 点击**新建密钥**
3. 记录：
   - **SecretId**
   - **SecretKey**

⚠️ **安全提示**：SecretKey 只显示一次，请妥善保存！

### 2.5 安装 CloudBase CLI（可选，用于手动部署）

如果需要本地手动部署（而非通过 GitHub Actions），需安装 CloudBase CLI：

```bash
npm install -g @cloudbase/cli

# 登录（会打开浏览器授权）
tcb login

# 验证登录状态
tcb env:list
```

> GitHub Actions 工作流中会自动安装 `@cloudbase/cli`，本地不装也不影响 CI/CD。

---

## 第三步：配置 GitHub Secrets

在 GitHub 仓库添加 CloudBase 的凭证，让 GitHub Actions 能部署。

### 3.1 进入 Secrets 配置页面

1. 访问 `https://github.com/amostodo/trading-toolkit`
2. 点击 **Settings** → 左侧 **Secrets and variables** → **Actions**
3. 点击 **New repository secret**

### 3.2 添加以下 4 个 Secrets

| Name | Value |
|------|-------|
| `TENCENT_SECRET_ID` | 第二步获取的 SecretId |
| `TENCENT_SECRET_KEY` | 第二步获取的 SecretKey |
| `CLOUDBASE_ENV_ID` | 环境 ID（如 `trading-toolkit-xxxxx`） |
| `CLOUDBASE_SERVICE_ID` | 服务 ID（如 `trading-toolkit-api`） |

每个 Secret 操作：
1. Name 填入上方名称
2. Secret 填入对应值
3. 点击 **Add secret**

---

## 第四步：配置后端环境变量（可选）

在 CloudBase 控制台为服务配置环境变量：

1. CloudBase 控制台 → 云托管 → 服务列表 → 你的服务
2. **服务设置** → **环境变量**
3. 添加以下变量（按需）：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `DATABASE_URL` | `sqlite:///trading_toolkit.db` | 数据库（默认 SQLite，容器重启后数据丢失） |
| `USE_MOCK` | `false` | 使用真实数据源 |
| `TUSHARE_TOKEN` | （你的 token） | 可选，用于 tushare 数据源 |
| `WX_APPID` | （你的 appid） | 可选，微信登录 |
| `WX_SECRET` | （你的 secret） | 可选，微信登录 |

> **数据库建议**：生产环境推荐使用腾讯云 MySQL，将 `DATABASE_URL` 改为：
> ```
> mysql+pymysql://user:password@host:3306/dbname?charset=utf8mb4
> ```

---

## 第五步：触发自动部署

### 方式一：推送代码自动部署

```bash
cd d:\Develop\GitHub\trading-toolkit
git add .
git commit -m "feat: 添加 CloudBase 部署工作流"
git push github main
```

推送后：
1. **Backend CI** 工作流先跑测试
2. **Backend Deploy to CloudBase** 工作流自动部署

### 方式二：手动触发

1. 访问 `https://github.com/amostodo/trading-toolkit/actions`
2. 左侧选择 **Backend Deploy to CloudBase**
3. 右侧点击 **Run workflow** → 选择 main 分支 → **Run workflow**

---

## 第六步：查看部署状态

### 6.1 查看 GitHub Actions

访问 `https://github.com/amostodo/trading-toolkit/actions`

- 🟡 黄色：正在运行
- ✅ 绿色：成功
- ❌ 红色：失败（点击查看日志）

### 6.2 查看 CloudBase 部署

1. CloudBase 控制台 → 云托管 → 服务列表 → 你的服务
2. **版本管理** 查看部署历史
3. **服务监控** 查看 QPS、响应时间

### 6.3 获取访问地址

部署成功后，在 CloudBase 控制台 → 云托管 → 服务列表 → 你的服务 → **访问地址** 中可以找到公网访问地址。

格式通常为：
```
https://<env-id>.service.tcloudbase.com/<service-path>
```

测试 API：
```bash
curl https://<env-id>.service.tcloudbase.com/<service-path>/api/v1/market/overview
```

> **提示**：实际路径以控制台显示为准，不同配置下路径格式可能不同。首次部署后建议在控制台确认访问地址。

---

## 第七步：前端配置后端地址

前端部署后，需要配置后端地址才能访问数据。

### 7.1 在前端设置页配置

1. 访问前端网站 `https://amostodo.github.io/trading-toolkit-web/`
2. 进入**设置**页
3. 在"云托管地址"填入 CloudBase 访问地址
4. 点击**保存配置**

### 7.2 或在前端代码中配置

修改 `trading-toolkit-web/.env.production`：

```env
VITE_API_BASE_URL=https://<env-id>.service.tcloudbase.com/<service-id>
```

---

## 常见问题

### Q1: GitHub Actions 部署失败

**原因**：Secrets 未配置或配置错误

**解决**：
1. 检查 Settings → Secrets 中 4 个变量是否都添加
2. 确认 SecretId / SecretKey 正确
3. 确认环境 ID 和服务 ID 正确

### Q2: CloudBase 部署超时

**原因**：akshare/pandas 等依赖较大，构建时间较长

**解决**：
- CloudBase 默认构建超时 10 分钟，一般够用
- 如果超时，可以在 Dockerfile 中优化依赖安装

### Q3: 部署成功但 API 无法访问

**原因**：端口不匹配或路径错误

**解决**：
1. 确认 Dockerfile 中 `EXPOSE 8080`
2. 确认 CloudBase 服务端口设置为 `8080`
3. 确认访问路径包含服务 ID

### Q4: 免费额度用完怎么办

CloudBase 按量付费，新用户有免费额度（具体额度以[官方文档](https://cloud.tencent.com/document/product/876/47818)为准），个人项目通常足够。超额后费用很低（约几元/月）。

### Q5: 想要更简单的部署方式

如果不熟悉 CLI 部署，可以用 CloudBase 的**代码托管**功能：

1. CloudBase 控制台 → 云托管 → 服务列表 → 新建服务
2. 选择**代码托管** → 连接 GitHub 仓库
3. 选择 `trading-toolkit` 仓库和 `cloudrun/` 目录
4. 每次推送代码自动部署（不需要 GitHub Actions 做 CD）

这样 CI 用 GitHub Actions，CD 用 CloudBase 代码托管自动部署。

### Q6: 如何查看服务日志和监控

1. **实时日志**：CloudBase 控制台 → 云托管 → 服务 → **日志管理**，可查看实时日志流
2. **监控指标**：服务 → **监控**，可查看 QPS、响应时间、错误率、内存/CPU 使用率
3. **历史日志**：支持按时间范围查询，便于排查线上问题
4. **告警配置**：在腾讯云**云监控**控制台可以为云托管服务设置告警规则（如错误率 > 5% 时发送通知）

### Q7: 云托管重启后数据库数据丢失

**原因**：云托管容器是临时性的，重启/重新部署后容器内的 SQLite 文件会被清除。

**解决**：生产环境建议使用外部数据库（如腾讯云 MySQL），避免数据丢失。

---

## 文件清单

| 文件 | 位置 | 作用 |
|------|------|------|
| `backend-ci.yml` | 后端 `.github/workflows/` | CI：安装依赖 + 跑测试 |
| `backend-deploy.yml` | 后端 `.github/workflows/` | CD：部署到 CloudBase |
| `Dockerfile` | 后端 `cloudrun/` | Docker 构建配置 |
| `requirements.txt` | 后端 `cloudrun/` | Python 依赖 |
