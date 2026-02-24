## 目标

* 使用 `data/QQQ.csv` 与 `data/TQQQ.csv` 完成 2000-01-03 至 2025-12-10 的策略回测。

* 输出交易记录 CSV、三类图表、绩效报告指标。

## 已知数据结构

* `QQQ.csv` 列：`Date, Open, Close, Gap%, 100MA, 200MA, 前高, 前高日期`（已内置 MA200；当样本不足时为 "0.0"）。

* `TQQQ.csv` 列：`Date, Close, Close`。

* 两文件均含日期 `2025-12-10`（已核验）。

## 关键假设

* 买入分批：基于初始资金 100,000 美元，将目标满仓拆为 5 个等额“资金分批”（每批 20% 的初始资金）。

* 交易成本：买卖均支付 0.1% 手续费；买入时以 `price * (1 + fee)` 约束整数股可买数量，卖出时净得 `price * qty * (1 - fee)`。

## 信号规则实现

* 趋势确认（QQQ）：`Close > MA200 * 1.04`；仅在 `MA200 > 0` 时有效。

* 精准切入（QQQ）：在趋势确认成立后，等待某一交易日满足 `QQQ_Close < QQQ_PrevClose * 0.99`，当日以 TQQQ 收盘价买入“下一批”。

* 连续分批：在趋势确认保持为真期间，每遇到符合的 “1% 回调日”依次买入下一批，直至 5 批完成或趋势失效。

* 防守清仓（QQQ）：`Close < MA200 * 0.97`，当日以 TQQQ 收盘价卖出全部持仓，重置分批计数。

## 回测流程

1. 读取与对齐

   * 加载两 CSV，按 `Date` 内连接。

   * 过滤区间 `[2000-01-03, 2025-12-10]`。

   * 将 `QQQ 200MA` 转为 `float`，无效（`0.0`）则该日不触发趋势/防守。

2. 状态管理

   * 现金初始：`100_000`；持仓数量初始：`0`；已买分批数：`0`。

   * 每日计算：`position_value = TQQQ_Close * position_qty`；`equity = cash + position_value`。

3. 买入逻辑

   * 条件：趋势为真且当日满足 1% 回调；`batches_bought < 5`。

   * 目标分批现金：`initial_capital*0.2`。(或者清仓后全部资金的 20%)

   * 可买股数：`floor( target_cash / (TQQQ_Close * (1 + fee)) )`；若为 0 则跳过。

   * 更新现金、持仓与记录交易。

4. 卖出逻辑

   * 条件：`QQQ_Close < MA200 * 0.97` 且 `position_qty > 0`。

   * 卖出全部：现金增加 `TQQQ_Close * qty * (1 - fee)`；清零持仓与分批计数。

   * 记录交易。

5. 交易记录与字段

   * `Date, Action, Qty, Price, Amount, Cash, PositionQty, PositionValue, TotalEquity, QQQ_Open, QQQ_Close, QQQ_200MA, QQQ_Gap%, QQQ_前高, QQQ_前高日期, TQQQ_Open, TQQQ_Close`。

6. 图表输出

   * 资产价值曲线：标注初始资金水平线。

   * QQQ 价格与 MA200 叠加：标注买卖点（基于交易记录）。

   * 仓位变化柱状图：每日持仓数量或持仓占比变化。

7. 绩效指标

   * 期末资产：最后一日 `equity`。

   * 年化收益率（CAGR）：`(final / initial) ** (365.25 / days) - 1`（以首尾自然日数计算）。

   * 最大回撤：基于每日 `equity` 计算历史高点回落比例的最小值。

   * 胜率：以每次“完整回合”（一次或多次分批的整体持仓，对应一次清仓）为单位，统计盈亏次数与比例。

   * 交易次数：买入笔数与卖出笔数。

8. 异常与边界处理

   * 跳过任何缺失/不可解析值的当日。

   * MA200 为 `0.0` 的前 200 日不触发信号。

   * 买入分批若因现金不足只能买 0 股则不记录交易。

   * 数据对齐只在双侧均有该日数据时计算与下单。

## 产出文件结构（建议）

* `scripts/backtest_tqqq.py`：主回测脚本。

* `output/trades.csv`：交易明细。

* `output/plots/equity.png`、`output/plots/qqq_ma200.png`、`output/plots/position.png`：图表 (图表上使用英文标注)。

* `output/performance.json`：绩效汇总。

* `README.md`：补充运行方式与依赖（如需 `matplotlib`）。

## 依赖与实现细节

* 读取/计算：使用标准库 `csv` 与 `datetime`，保持与现有 `refresh_data.py` 风格一致；绘图使用 `matplotlib`。

* 不引入 `pandas`，避免额外依赖；若您偏好 `pandas`，可在确认后改为 `pandas` 实现并提供 `requirements.txt`。

## 验证与复现

* 运行脚本生成 CSV 与图表后，人工校验：

  * 核对部分日期的趋势阈值与买卖点是否一致。

  * 随机抽样核对手续费计算与整数股约束。

  * 检查绩效指标与曲线是否与交易记录一致性。

## 后续可选增强

* 增加“趋势保持”的宽容窗口（如允许短暂跌破 1.04 但不立即停止分批）。
