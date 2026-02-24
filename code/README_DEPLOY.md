# TQQQ 本地化自动交易系统部署指南

本系统基于 Python 和 Yahoo Finance API 实现，能够自动获取美股数据、运行 TQQQ 双核策略，并发送交易信号提醒。

## 1. 系统架构
*   **数据源**: Yahoo Finance (`yfinance`) - 免费、每日更新。
*   **策略引擎**: `src/strategy_engine.py` - 实现了 MA200/MA20、Anti-V、T+1 等核心逻辑。
*   **调度器**: `src/scheduler.py` - 每日定时运行。
*   **通知**: `src/notifier.py` - 支持本地日志、桌面弹窗及邮件通知。

## 2. 部署步骤

### 2.1 环境准备
确保已安装 Python 3.8+。

```bash
# 1. 创建虚拟环境 (推荐)
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt
```

### 2.2 配置通知 (可选)
如果需要接收邮件提醒，请创建 `.env` 文件：

```bash
touch .env
```
在 `.env` 中填入以下内容 (以 Gmail 为例)：
```ini
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_TO=your_email@gmail.com
```
*注：Gmail 需要开启两步验证并生成应用专用密码 (App Password)。*

### 2.3 运行系统

**方式一：前台运行 (调试用)**
```bash
python run.py
```
程序将启动并在每天 16:30 (默认配置) 运行策略。

**方式二：后台运行 (生产环境)**
使用 `nohup` 让程序在后台持续运行：
```bash
nohup python run.py > output.log 2>&1 &
```
查看运行日志：
```bash
tail -f code/logs/strategy.log
```

## 3. 监控与维护

### 3.1 日志文件
所有运行日志保存在 `code/logs/strategy.log`。
*   `INFO`: 正常运行记录。
*   `WARNING`: 反转过滤拦截、数据缺失等非致命问题。
*   `ERROR`: 严重错误 (网络中断、API 故障)，会触发邮件报警。

### 3.2 状态文件
策略状态保存在 `strategy_state.json`。
*   **切勿手动修改此文件**，除非你想重置策略状态 (如 `risk_off_days` 计数)。
*   若需重置，直接删除该 JSON 文件即可，下次运行会自动初始化。

### 3.3 故障排查
*   **无数据**: 检查网络是否能访问 Yahoo Finance。
*   **不发邮件**: 检查 `.env` 配置及 SMTP 端口是否被防火墙拦截。
*   **任务未执行**: 检查系统时间与 `config.py` 中的 `SCHEDULE_TIME` 时区是否一致。

## 4. 目录结构
```
code/
├── DATA_SOURCES.md       # 数据源文档
├── TQQQ.md               # 策略说明书
├── requirements.txt      # 依赖列表
├── run.py                # 启动脚本
├── strategy_state.json   # 运行时状态存储 (自动生成)
├── src/
│   ├── config.py         # 配置文件
│   ├── data_fetcher.py   # 数据获取模块
│   ├── notifier.py       # 通知模块
│   ├── scheduler.py      # 调度模块
│   └── strategy_engine.py# 策略核心逻辑
└── logs/                 # 日志目录
```
