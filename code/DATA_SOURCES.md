# 免费可靠金融数据源清单 (Free & Reliable Financial Data Sources)

以下是一份经过筛选的、适用于个人量化投资和自动化交易的高质量免费数据源清单。

## 1. Yahoo Finance (yfinance)
**首选推荐**。目前最流行的非官方 Python 接口，数据覆盖面广，无需注册 API Key。

*   **数据类型**: 股票、ETF、指数、外汇、加密货币的历史行情 (OHLCV)、实时价格 (有延迟)、财务报表、基本面信息。
*   **更新频率**: 每日更新 (历史数据)，实时 (盘中，通常延迟 15 分钟)。
*   **API 访问方式**: Python 库 `yfinance` (底层调用 Yahoo Finance API)。
*   **请求限制**: 无明确官方限制，但过于频繁 (如每秒数百次) 可能会被 IP 封禁。建议每秒请求不超过 5 次。
*   **数据格式**: Pandas DataFrame, JSON.
*   **认证要求**: 无需认证。
*   **使用条款**: 仅供个人研究和非商业用途。
*   **代码示例**:
    ```python
    import yfinance as yf
    data = yf.download("QQQ", start="2020-01-01", end="2023-12-31")
    print(data.head())
    ```

## 2. Alpha Vantage
老牌免费 API 提供商，提供标准化的 JSON/CSV 数据。

*   **数据类型**: 股票、外汇、加密货币、技术指标 (MA, RSI 等直接返回计算结果)。
*   **更新频率**: 每日/实时。
*   **API 访问方式**: HTTP REST API.
*   **请求限制**: **免费版限制严格** - 每分钟 5 次，每天 500 次。
*   **数据格式**: JSON, CSV.
*   **认证要求**: 需要申请免费 API Key (邮箱注册即可)。
*   **使用条款**: 个人非商业用途。
*   **适用场景**: 需要官方计算好的技术指标，或者作为 Yahoo Finance 的备用源。

## 3. Polygon.io (Basic Tier)
专业级数据源，提供高质量的 WebSocket 和 REST API。

*   **数据类型**: 美股、外汇、加密货币。
*   **更新频率**: 免费版仅提供 **EOD (End of Day)** 历史数据，无实时数据。
*   **API 访问方式**: HTTP REST API, WebSocket.
*   **请求限制**: 免费版每分钟 5 次请求。
*   **数据格式**: JSON.
*   **认证要求**: 需要注册 API Key。
*   **使用条款**: 个人用途。
*   **适用场景**: 对数据质量要求极高，且只需要日线级别收盘数据的策略。

## 4. Stooq
波兰的金融数据网站，无需 API Key 即可下载 CSV，非常适合获取长期历史数据。

*   **数据类型**: 全球指数、股票、ETF、期货、宏观经济数据。
*   **更新频率**: 每日更新。
*   **API 访问方式**: 直接通过 URL 构造下载 CSV 文件，或使用 `pandas_datareader`。
*   **请求限制**: 较为宽松。
*   **数据格式**: CSV.
*   **认证要求**: 无。
*   **代码示例**:
    ```python
    import pandas_datareader.data as web
    df = web.DataReader('^NDX', 'stooq')
    ```

## 5. Tiingo
数据质量极高，包含新闻源和加密货币数据。

*   **数据类型**: 美股 (含复权数据)、加密货币、新闻。
*   **更新频率**: EOD (日终) 数据。
*   **API 访问方式**: HTTP REST API.
*   **请求限制**: 免费版每天 500 个不同标的，每小时 500 次请求，每月 20,000 次请求。
*   **数据格式**: JSON, CSV.
*   **认证要求**: 需要注册 API Key。
*   **特色**: 提供非常准确的复权 (Adjusted) 价格，适合回测。

---

## 推荐组合方案

对于 **TQQQ 双核策略**，推荐使用 **Yahoo Finance (`yfinance`)** 作为主数据源，理由如下：
1.  **完全免费且无硬性 Key 限制**，适合长期运行的脚本。
2.  **数据字段完整**：包含 Open, High, Low, Close, Volume，足以计算策略所需的 MA200, MA20, ATH 等指标。
3.  **Python 生态友好**：直接返回 Pandas DataFrame，极易与 `pandas` 集成进行向量化计算。

若 `yfinance` 出现服务不稳定，可切换至 **Alpha Vantage** 作为备用（需注意每分钟 5 次的限制，代码中需加入 `time.sleep`）。
