# tracknorm · 物流轨迹采集、状态归一与停滞预警台

> 迅联供应链 · 客户服务部（20 人）把顺达快递 / 安能快运 / 德坤大件 3 家承运商的轨迹码表，
> 统一成自家 8 个状态，并自动揪出「停在半路」的大件单——先把客户投诉变成主动说明。

## 真实场景

- **模拟客户**：迅联供应链（杭州，供应链服务商，客户服务部 20 人），日均聚合 2000 单、3 家承运商轨迹。
- **现有工作流**：客服每天从 3 个承运商后台导出轨迹 CSV，用 Excel 把「已揽收 / `COLLECTED` /
  `PICKUP_DONE`」手工翻译成自家 8 个状态；再人工翻列表找停太久的大件单，最后手工写客户说明。
- **三个痛点**：① 状态码不统一，看板口径混乱；② 停滞靠人发现，客户先投诉；③ 轨迹乱序 / 重复回推，
  「最近状态」经常是错的。
- **上下游**：上游 = 承运商轨迹 API（内置 mock，含 429 限流）→ 本系统替代「人工翻译 + Excel 盯异常」
  → 下游 = 客服工单处置与客户查询页（`client` 角色只读）。
- **一天的工作剧本**：08:40 运营主管确认 3 家承运商配额 → 09:00 定时任务拉取 200 单轨迹（2 次 429 退避）
  → 归一跑出覆盖率 97.5% 与 5 条回退冲突 → 客服在预警看板认领 6 条停滞单中的 2 条并处置
  → 运营主管发布映射 v2 处理 3 条冲突 → 导出客户延迟说明 CSV 给商家。

## 角色权限

| 角色 | 账号 | 能做什么 |
|---|---|---|
| `admin` 运营主管 | `admin@tracknorm.io` | 承运商配额/频率、映射规则版本创建与启用、拉取与归一、预警处置、数据质量与审计 |
| `ops` 客服专员 | `ops@tracknorm.io` | 拉取/归一、预警认领与处置、延迟说明导出；不可改承运商与映射版本（403） |
| `client` 商家只读 | `client@tracknorm.io` | 只看自己（`client@tracknorm.io` 名下）运单轨迹与延迟说明导出；调管理接口真实 403 |

密码统一 `Demo@2026`。

## 主要功能

1. **运单总览**：8 个归一状态分桶 + 承运商/状态/关键字筛选，等宽时间戳与状态灯。
2. **运单详情**：原始轨迹事件（承运商码、seq、到达顺序）与归一后垂直时间轴并排，展示映射命中分数
   （精确 1.0 / 别名 0.8 / 模糊 0.5–0.7）与冲突标记。
3. **映射规则管理**：版本 v1/v2 对比、规则命中数、按版本重算覆盖率与冲突、创建并启用 v2。
4. **停滞预警看板**：按承运商×线路×阶段的基线（P50+MAD）稳健 z 分级 warn/alert/critical，
   认领 → 处置留痕，抽屉里展示归一轨迹与预计送达偏差。
5. **承运商配置 + 数据质量报表**：配额/频率/启停，拉取统计与 429 命中，覆盖率/重复率/乱序/冲突 → 质量分。
6. **登录**：管制台风格，雷达扫描装饰。

## 两个真算算法

### 算法 1 轨迹归一与乱序修复（`backend/src/services/normalize_engine.py`）

- 稳定排序：`(event_time, seq, carrier_event_id)`，修复乱序到达；
- 窗口去重：同归一状态 + 同地点、与上一条保留事件间隔 ≤ **30 分钟** → 重复回推丢弃；
- 状态机：只允许前向/同阶段推进（异常/退件特判），回退事件标 `conflict` 且不改变当前状态；
- 映射打分：精确 `1.0` / 别名 `0.8` / 模糊 `0.5–0.7` / 未命中 `<0.5` 记 0，取最高分（同分专用承运商优先）；
- 输出：归一轨迹、当前状态、覆盖率（命中映射事件 / 原始事件）、冲突/重复/乱序/未命中明细。

seed 数据：1200 事件中覆盖 1170 → **覆盖率 97.5%**；v1 冲突 **5 条**，v2 启用后剩 2 条。

### 算法 2 停滞检测（`backend/src/services/stagnation_engine.py`）

- 基线：已签收运单在「承运商 × 起点大区→目的地大区 × 阶段」的停留时长 P50 与 MAD；
- 稳健 z = `0.6745 × (当前停留 − P50) / max(MAD, 1.0)`，`z ≥ 3.5` 判停滞（只取停留偏长方向，快进不误报）；
- 分级：`warn` 3.5–5 / `alert` 5–8 / `critical` ≥ 8（seed 6 条：3 warn / 2 alert / 1 critical）；
- 失败态：基线样本 < 5 → `insufficient_baseline`（不出预警，计入统计）；
- 预计送达 = 最后事件时间 + 后续各段基线 P50 之和（已过期取当前时刻），偏差（小时）= 预计 − 承诺。

## 快速启动

```bash
cp .env.example .env
docker compose up -d --build          # 5 服务：frontend/backend/worker/db/redis
docker compose ps                     # 等 5/5 healthy（首次含 seed，约 60–120s）
```

- 前端：http://localhost:18242
- 后端：http://localhost:19242/api/health
- MySQL：`127.0.0.1:17742`（库/用户 `tracknorm`，密码见 `.env`）

seed 在 backend 启动时自动执行一次（`SEED_DEMO=true`），也可手动重跑（幂等）：

```bash
docker compose exec backend python scripts/seed_demo.py
# SEED_SUMMARY brand=tracknorm carriers=3 waybills=200 events=1200 alerts=6 users=3
```

## 本地开发

```bash
# 后端
cd backend && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
uvicorn src.main:app --reload --port 8000
# 前端
cd frontend && npm install && npm run dev   # 5173，/api 代理到 19242
```

> 后端所有路由同时挂载 `/api/...` 与根路径；Nginx 把 `/api/` 反代到 `backend:8000/` 并剥掉前缀，
> 因此前端统一请求 `/api/...`。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18.3 + TypeScript 5.6 + Vite 5（Nginx 1.27 托管 dist） |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + PyMySQL |
| 异步 | Celery 5.4（worker + beat：心跳 / 30 分钟拉取归一 / 15 分钟停滞扫描） |
| 存储 | MySQL 8.0（命名卷）+ Redis 7（限流、跑批缓存、演示锚点） |
| 采集 | 承运商 API **内置 mock**（`backend/src/services/carrier_mock.py`），含 2 次 429 退避 |

## 目录

```
backend/src/{config,constants,utils,middlewares,models,schemas,services,controllers,routes}
backend/scripts/{seed_demo.py,seed_data.py,demo_config.py}
backend/migrations/0001_initial.sql
frontend/src/{api,stores,types,components/common,components/layout,hooks,pages,router,utils,constants,styles}
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 18242 / 19242 / 17742 | 端口映射 |
| `SEED_DEMO` | `true` | 启动时自动 seed |
| `JWT_SECRET` | 见 `.env.example` | JWT 签名 |
| `REDIS_URL` | `redis://redis:6379/0` | 限流 / 缓存 / 锚点 |
| `RATE_LIMIT_PER_MINUTE` | 300 | 全局限流 |
| `RATE_LIMIT_PULL_PER_MINUTE` | 20 | 拉取/归一单独配额 |
| `MOCK_429_BUDGET` | 2 | 每次拉取 mock 返回 429 的次数 |

## 共享枚举出现位置

- `NormalizedStatus`（8 个归一状态）：`backend/src/constants/enums.py`、`frontend/src/constants/enums.ts`、
  `backend/src/models/*.py`、`frontend/src/components/common/StatusLamp.tsx`、`.../TrackTimeline.tsx`。
- `AlertSeverity` / `AlertStatus` / `Disposition`：`backend/src/constants/enums.py`、`frontend/src/constants/enums.ts`、
  `backend/src/services/{alert_service,stagnation_engine}.py`、`frontend/src/pages/Alerts.tsx`。
- `MatchType`（exact/alias/fuzzy）：`backend/src/constants/enums.py`、`frontend/src/constants/enums.ts`、
  `backend/src/services/{normalize_engine,mapping_service}.py`、`frontend/src/pages/Mappings.tsx`。

## 已知边界

- 承运商接口为后端内置 mock，不访问外网；真实接入需替换 `carrier_mock.py` 并配置鉴权。
- mock 只返回标准码表事件；重复回推/乱序/非法回退/未知码由 seed 固定注入（见 TESTING「已知差异」）。
- 演示数据以 seed 锚定时刻计算停留，保证重复跑批与停滞条数可复现。

## License

MIT（演示项目，数据均为虚构）。
