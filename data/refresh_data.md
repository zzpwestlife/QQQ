# 刷数据脚本说明

本脚本用于从仅包含 `Date, Open, Close` 的原始 CSV 数据生成以下列：`Gap%`, `100MA`, `200MA`, `前高`, `前高日期`，并输出为标准化的结果文件。

**脚本位置**
- `/Users/admin/openSource/QQQ/refresh_data.py`（源码参考：`/Users/admin/openSource/QQQ/refresh_data.py:1`）

## 输入与输出
- 输入文件（原始）：至少包含表头与以下三列
  - `Date`：日期（`YYYY-MM-DD`）
  - `Open`：开盘价（数字）
  - `Close`：收盘价（数字）
- 输出文件（结果）：表头固定为  
  `Date, Open, Close, Gap%, 100MA, 200MA, 前高, 前高日期`

## 生成规则
- `Gap%`：当日开盘价相对前一日收盘价的变化百分比
  - 计算公式：`(Open_today - Close_prev) / Close_prev * 100`，格式 `+/-X.X%`
  - 若前一日收盘价不存在或为 0，则记为 `+0.0%`
- `100MA`：`Close` 的 100 日简单移动平均（SMA）
  - 前 99 日不足以凑满 100 个样本，记为 `0.0`
  - 满足后按最近 100 个收盘价的平均值，保留两位小数
- `200MA`：`Close` 的 200 日简单移动平均（SMA）
  - 前 199 日不足以凑满 200 个样本，记为 `0.0`
  - 满足后按最近 200 个收盘价的平均值，保留两位小数
- `前高`/`前高日期`：截至「前一日」的历史最高收盘价与其日期
  - 第一行由于没有历史，`前高` 与 `前高日期` 为空
  - 之后每一行使用「不含当日」的历史最高收盘价与日期
  - 当日若创新高，仅用于更新后续行的历史记录

## 使用方法
- 就地刷新当前文件：

```bash
python3 /Users/admin/openSource/QQQ/refresh_data.py \
  --input /Users/admin/openSource/QQQ/QQQ.csv \
  --output /Users/admin/openSource/QQQ/QQQ.csv
```

- 从原始数据生成到新文件：

```bash
python3 /Users/admin/openSource/QQQ/refresh_data.py \
  --input /path/to/raw.csv \
  --output /path/to/output.csv
```

### 参数说明
- `--input`：输入 CSV 路径（默认：`QQQ.csv`，相对当前目录）
- `--output`：输出 CSV 路径（不传则覆盖输入文件）

## 实现细节
- 原子写入：先写入临时文件（`<output>.tmp`），完成后替换目标文件，避免中途失败导致输出损坏
- 数字格式：`Open`、`Close`、`MA` 输出保留两位小数；`Gap%` 保留一位小数并带符号
- 行健壮性：若行存在缺失或非数值错误，将跳过该行

## 示例
表头：
```
Date, Open, Close, Gap%, 100MA, 200MA, 前高, 前高日期
```
示例数据（片段）：
```
1999-03-10,51.13,51.06,+0.0%,0.0,0.0,,
1999-07-30,57.13,56.59,+0.4%,54.37,0.0,61.38,1999-07-16
```

## 备注
- 如需将均线改为 EMA（指数移动平均）或调整小数位数等格式，请提出需求即可调整脚本。
