# 开发进度

按时间倒序。这里写「做了什么、为什么这么做」；产品说明仍看仓库根目录 README。

---

## 2026-09-12 · v0.5a 决策质量

### 背景

开仓流水线已经完整：Delta 分档、财报/FOMC 硬门控、宏观软标签、新闻侦察、LLM 终审、到期损益图。产品断层在持仓管理，但那一块需要状态对象。先补开仓决策本身缺的一层：**这约贵不贵、行权价离预期波动有多远、大盘现在什么状态**。

刻意不做：

- 不落库、不存每日 IV 序列，因此也没有 IV Percentile
- 不做全市场扫描器
- 不改选档主规则（仍是 Delta 带内最近 + NBBO 优先）
- 不加铁鹰 / Collar / 持仓管理

IV 体制用 **当前 ATM IV / 20 日已实现波动**。没有历史分位数之前，这是当天就能用、也不会假装「IVP=72」的做法。

### 公式与规则

**Expected Move（1σ）**

```text
EM% = IV × √(DTE / 365)
EM$ = spot × EM%
cushion% = |strike − spot| / spot   （Put 在现价下方，Call 在上方）
inside EM = cushion% < EM%
```

用该合约自己的 IV 和 DTE，不用历史期权库。ATM 合约的 EM 挂在 snapshot 上，给刻度尺用。

**已实现波动**

对数收益、样本标准差、×√252。窗口 20 / 60 / 120。样本不足 10 个交易日则该项为空。

**IV 体制（相对 HV20）**

| IV / HV20 | 标签 |
| ---: | --- |
| < 0.85 | `low` |
| < 1.15 | `normal` |
| < 1.50 | `high` |
| ≥ 1.50 | `rich` |

卖权利金时 `low` 表示期权相对近期股价波动偏便宜，启发式改走保守档；`high` / `rich` 不作为无视日历或事件的理由。

**市场体制（每轮一次，不是每只股票一次）**

输入：VIX、VIX3M/VIX 期限结构、SPY 相对 20/50 日均。

| 条件 | 标签 |
| --- | --- |
| VIX ≥ 30，或 VIX ≥ 25 且 SPY 低于 50 日均 | `risk_off` |
| VIX ≥ 22，或 SPY 低于 50 日均 | `caution` |
| VIX < 14 且 SPY 高于 20 与 50 日均 | `risk_on` |
| 其余 | `neutral` |

VIX 期限倒挂（VIX3M/VIX < 0.95）上调一档。`caution` / `risk_off` 只是 **reduce**（偏向保守档），单独不会 SKIP。Yahoo 拉失败则这一层缺席，流水线继续。

**合约评分 0–100**

给两档候选排序参考，不是下单指令。权重：Delta 贴合 25、IV 相对 HV 20、权利金/占用资金 20、价差 15、相对 EM 的安全垫 10、流动性 10。缺 IV 时去掉该片并按剩余权重归一。Last print 价差分为 0。选档函数 `select_bucket()` 不变，分数事后挂上。

启发式额外：标准档在 EM 内、保守档在 EM 外 → 改用保守档。

### 接到哪

- `TickerSnapshot.iv_context`、`BucketCandidate.score`、`DeskRun.market`
- 流水线在筛链前先发 `regime_started` / `regime_done`
- LLM 系统提示和 snapshot 正文带上 IV/EM/score/市场；启发式无 LLM 时走同一套 reduce
- Web：市场体制卡片、IV 网格、EM 刻度尺、评分列；移动端网格两列、刻度尺全宽、表继续横向滑
- CLI / markdown 报告同步这些字段
- 中英：`option_desk/i18n.py` 与 `web/src/i18n.ts`

### 文件

| 路径 | 作用 |
| --- | --- |
| `option_desk/chain/quality.py` | 纯计算：EM、HV、IV 体制、市场规则、评分 |
| `option_desk/chain/market.py` | yfinance 拉收盘价；失败则空 |
| `option_desk/chain/screener.py` | 筛完后挂 IV 上下文和分数 |
| `option_desk/pipeline.py` | 每轮一次市场体制 |
| `option_desk/agents/desk.py` | 提示词 + 启发式 reduce |
| `option_desk/schemas.py` | `IvContext` / `ContractScore` / `MarketRegime` |
| `web/src/QualityPanel.tsx` | IV 网格、EM 尺、市场卡片 |
| `tests/test_quality.py` | 公式与体制规则 |
| `tests/test_desk.py` | risk_off / 低 IV / 标准档在 EM 内 → 保守档 |

### 已知边界

- `--as-of` 仍然只改日历窗口；IV/HV/EM 用的是当前 yfinance 快照
- HV 每个标的多一次历史行情请求，市场体制每轮四次（VIX、VIX3M、SPY、QQQ）；失败不阻断分析
- 评分是排序辅助。终审仍只能从已有档位里挑 `contract_id`
