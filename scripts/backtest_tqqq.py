import csv
import os
from datetime import datetime
from math import floor


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
QQQ_PATH = os.path.join(DATA_DIR, "QQQ.csv")
TQQQ_PATH = os.path.join(DATA_DIR, "TQQQ.csv")
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
PLOTS_DIR = os.path.join(OUTPUT_DIR, "plots")

START_DATE = "2000-01-03"
END_DATE = "2025-12-10"
INITIAL_CAPITAL = 100_000.0
FEE_RATE = 0.001
TRANCHE_COUNT = 5
TRANCHE_SIZE = INITIAL_CAPITAL * (1.0 / TRANCHE_COUNT)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def read_qqq(path):
    data = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("Date")
            if not d:
                continue
            try:
                rec = {
                    "Date": d,
                    "Open": float(row.get("Open", "0") or "0"),
                    "Close": float(row.get("Close", "0") or "0"),
                    "Gap%": row.get("Gap%", "") or "",
                    "100MA": row.get("100MA", "") or "",
                    "200MA": float(row.get("200MA", "0") or "0"),
                    "PrevHigh": row.get("前高", "") or "",
                    "PrevHighDate": row.get("前高日期", "") or "",
                }
            except ValueError:
                continue
            data[d] = rec
    return data


def read_tqqq(path):
    data = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("Date")
            if not d:
                continue
            try:
                rec = {
                    "Date": d,
                    "Open": float(row.get("Open", "0") or "0"),
                    "Close": float(row.get("Close", "0") or "0"),
                }
            except ValueError:
                continue
            data[d] = rec
    return data


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)


def backtest(
    start_date_str: str = START_DATE,
    end_date_str: str = END_DATE,
    initial_capital: float = INITIAL_CAPITAL,
    fee_rate: float = FEE_RATE,
    tranche_count: int = TRANCHE_COUNT,
):
    qqq = read_qqq(QQQ_PATH)
    tqqq = read_tqqq(TQQQ_PATH)
    ensure_dirs()

    start = parse_date(start_date_str)
    end = parse_date(end_date_str)

    dates = sorted(set(qqq.keys()).intersection(tqqq.keys()), key=parse_date)
    dates = [d for d in dates if start <= parse_date(d) <= end]
    if not dates:
        raise RuntimeError("No overlapping dates in the requested range")

    cash = initial_capital
    qty = 0
    batches_bought = 0
    buy_cost_with_fee = 0.0
    tranche_size = initial_capital * (1.0 / tranche_count)

    equity_curve = []
    trades = []
    prev_close_qqq = None
    first_equity_date = parse_date(dates[0])
    last_equity_date = parse_date(dates[-1])

    for d in dates:
        q = qqq[d]
        t = tqqq[d]
        q_close = q["Close"]
        q_ma200 = q["200MA"]
        t_close = t["Close"]
        t_open = t["Open"]

        position_value = qty * t_close
        equity = cash + position_value
        equity_curve.append({"Date": d, "Equity": equity, "Cash": cash, "Qty": qty, "PositionValue": position_value})

        trend_ok = q_ma200 > 0 and q_close > q_ma200 * 1.04
        pullback_ok = prev_close_qqq is not None and q_close < prev_close_qqq * 0.99
        defend_sell = q_ma200 > 0 and q_close < q_ma200 * 0.97

        if defend_sell and qty > 0:
            proceeds = t_close * qty * (1.0 - fee_rate)
            cash += proceeds
            pnl = proceeds - buy_cost_with_fee
            trades.append({
                "Date": d,
                "Action": "Sell",
                "Qty": qty,
                "Price": t_close,
                "Amount": proceeds,
                "Cash": cash,
                "PositionQty": 0,
                "PositionValue": 0.0,
                "TotalEquity": cash,
                "QQQ_Open": q["Open"],
                "QQQ_Close": q_close,
                "QQQ_200MA": q_ma200,
                "QQQ_Gap%": q["Gap%"],
                "QQQ_前高": q["PrevHigh"],
                "QQQ_前高日期": q["PrevHighDate"],
                "TQQQ_Open": t_open,
                "TQQQ_Close": t_close,
                "PnL": pnl,
            })
            qty = 0
            batches_bought = 0
            buy_cost_with_fee = 0.0
            position_value = 0.0
            equity = cash

        elif trend_ok and pullback_ok and batches_bought < tranche_count:
            price_with_fee = t_close * (1.0 + fee_rate)
            max_cash = min(tranche_size, cash)
            buy_qty = int(floor(max_cash / price_with_fee))
            if buy_qty > 0:
                cost = t_close * buy_qty
                fee = cost * fee_rate
                total = cost + fee
                cash -= total
                qty += buy_qty
                buy_cost_with_fee += total
                batches_bought += 1
                position_value = qty * t_close
                equity = cash + position_value
                trades.append({
                    "Date": d,
                    "Action": "Buy",
                    "Qty": buy_qty,
                    "Price": t_close,
                    "Amount": total,
                    "Cash": cash,
                    "PositionQty": qty,
                    "PositionValue": position_value,
                    "TotalEquity": equity,
                    "QQQ_Open": q["Open"],
                    "QQQ_Close": q_close,
                    "QQQ_200MA": q_ma200,
                    "QQQ_Gap%": q["Gap%"],
                    "QQQ_前高": q["PrevHigh"],
                    "QQQ_前高日期": q["PrevHighDate"],
                    "TQQQ_Open": t_open,
                    "TQQQ_Close": t_close,
                })

        prev_close_qqq = q_close

    write_trades(os.path.join(OUTPUT_DIR, "trades.csv"), trades)
    perf = compute_performance(equity_curve, trades, initial_capital)
    write_performance(os.path.join(OUTPUT_DIR, "performance.json"), perf)
    plot_outputs(equity_curve, trades, dates, qqq)
    return {"equity_curve": equity_curve, "trades": trades, "performance": perf}


def write_trades(path, trades):
    fields = [
        "Date",
        "Action",
        "Qty",
        "Price",
        "Amount",
        "Cash",
        "PositionQty",
        "PositionValue",
        "TotalEquity",
        "QQQ_Open",
        "QQQ_Close",
        "QQQ_200MA",
        "QQQ_Gap%",
        "QQQ_前高",
        "QQQ_前高日期",
        "TQQQ_Open",
        "TQQQ_Close",
        "PnL",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in trades:
            writer.writerow(r)


def compute_performance(equity_curve, trades, initial_capital: float):
    if not equity_curve:
        return {
            "final_equity": initial_capital,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "buy_trades": 0,
            "sell_trades": 0,
        }
    start_date = parse_date(equity_curve[0]["Date"])
    end_date = parse_date(equity_curve[-1]["Date"])
    days = (end_date - start_date).days or 1
    final = equity_curve[-1]["Equity"]
    cagr = (final / initial_capital) ** (365.25 / days) - 1.0
    peak = -1e18
    max_dd = 0.0
    for r in equity_curve:
        e = r["Equity"]
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak
            if dd < max_dd:
                max_dd = dd
    sell_trades = [t for t in trades if t.get("Action") == "Sell"]
    wins = 0
    total_rounds = len(sell_trades)
    for s in sell_trades:
        if s.get("PnL", 0.0) > 0:
            wins += 1
    win_rate = (wins / total_rounds) if total_rounds > 0 else 0.0
    buy_count = sum(1 for t in trades if t.get("Action") == "Buy")
    sell_count = total_rounds
    return {
        "final_equity": round(final, 2),
        "cagr": round(cagr, 6),
        "max_drawdown": round(max_dd, 6),
        "win_rate": round(win_rate, 6),
        "buy_trades": buy_count,
        "sell_trades": sell_count,
        "period_days": days,
    }


def write_performance(path, perf):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=2)


def plot_outputs(equity_curve, trades, dates, qqq):
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    x = [parse_date(r["Date"]) for r in equity_curve]
    y = [r["Equity"] for r in equity_curve]
    plt.figure(figsize=(12, 5))
    plt.plot(x, y, label="Equity")
    plt.axhline(equity_curve[0]["Equity"], color="gray", linestyle="--", label="Initial")
    plt.legend()
    plt.title("Equity Curve")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "equity.png"))
    plt.close()

    q_dates = [parse_date(d) for d in dates]
    q_close = [qqq[d]["Close"] for d in dates]
    q_ma200 = [qqq[d]["200MA"] for d in dates]
    plt.figure(figsize=(12, 5))
    plt.plot(q_dates, q_close, label="QQQ Close")
    plt.plot(q_dates, q_ma200, label="QQQ MA200")
    buy_dates = [parse_date(t["Date"]) for t in trades if t["Action"] == "Buy"]
    buy_prices = []
    for t in trades:
        if t["Action"] == "Buy":
            d = t["Date"]
            buy_prices.append(qqq[d]["Close"])
    sell_dates = [parse_date(t["Date"]) for t in trades if t["Action"] == "Sell"]
    sell_prices = []
    for t in trades:
        if t["Action"] == "Sell":
            d = t["Date"]
            sell_prices.append(qqq[d]["Close"])
    if buy_dates:
        plt.scatter(buy_dates, buy_prices, marker="^", color="green", label="Buy")
    if sell_dates:
        plt.scatter(sell_dates, sell_prices, marker="v", color="red", label="Sell")
    plt.legend()
    plt.title("QQQ Close and MA200")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "qqq_ma200.png"))
    plt.close()

    pos_y = [r["Qty"] for r in equity_curve]
    plt.figure(figsize=(12, 3))
    plt.bar(x, pos_y, width=2)
    plt.title("Position Quantity")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "position.png"))
    plt.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=START_DATE)
    parser.add_argument("--end", default=END_DATE)
    parser.add_argument("--initial", type=float, default=INITIAL_CAPITAL)
    parser.add_argument("--fee", type=float, default=FEE_RATE)
    parser.add_argument("--tranches", type=int, default=TRANCHE_COUNT)
    args = parser.parse_args()
    backtest(
        start_date_str=args.start,
        end_date_str=args.end,
        initial_capital=args.initial,
        fee_rate=args.fee,
        tranche_count=args.tranches,
    )
