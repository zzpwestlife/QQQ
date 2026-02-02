import csv
import argparse
import os


def format_gap(prev_close, today_open):
    if prev_close is None or prev_close == 0:
        return "+0.0%"
    gap = (today_open - prev_close) / prev_close * 100.0
    return f"{gap:+.1f}%"


def sma(values, window):
    if len(values) < window:
        return "0.0"
    return f"{(sum(values[-window:]) / float(window)):.2f}"


def process(input_path, output_path):
    with open(input_path, "r", encoding="utf-8", newline="") as f_in, open(
        output_path, "w", encoding="utf-8", newline=""
    ) as f_out:
        reader = csv.DictReader(f_in)
        out_fields = ["Date", "Open", "Close", "Gap%", "100MA", "200MA", "前高", "前高日期"]
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        writer.writeheader()

        closes = []
        prev_close = None
        max_close = None
        max_date = ""

        for row in reader:
            try:
                date = row["Date"]
                open_ = float(row["Open"])
                close_ = float(row["Close"])
            except (KeyError, ValueError):
                continue

            gap = format_gap(prev_close, open_)
            closes.append(close_)
            ma100 = sma(closes, 100)
            ma200 = sma(closes, 200)

            if max_close is None:
                prev_high_val = ""
                prev_high_date = ""
                max_close = close_
                max_date = date
            else:
                prev_high_val = f"{max_close:.2f}"
                prev_high_date = max_date
                if close_ > max_close:
                    max_close = close_
                    max_date = date

            writer.writerow(
                {
                    "Date": date,
                    "Open": f"{open_:.2f}",
                    "Close": f"{close_:.2f}",
                    "Gap%": gap,
                    "100MA": ma100,
                    "200MA": ma200,
                    "前高": prev_high_val,
                    "前高日期": prev_high_date,
                }
            )

            prev_close = close_


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="QQQ.csv")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    in_path = os.path.abspath(args.input)
    out_path = os.path.abspath(args.output) if args.output else in_path

    tmp_path = out_path + ".tmp"
    process(in_path, tmp_path)
    os.replace(tmp_path, out_path)


if __name__ == "__main__":
    main()
