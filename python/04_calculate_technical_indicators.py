from pathlib import Path
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

IN_FILE = BASE_DIR / "data" / "processed" / "fact_price_daily.csv"
OUT_FILE = BASE_DIR / "data" / "processed" / "fact_technical_indicators.csv"


def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def main():
    df = pd.read_csv(IN_FILE)

    # Chuẩn hóa tên cột
    df.columns = [
        str(col).lower().strip().replace(" ", "_")
        for col in df.columns
    ]

    # Tự nhận diện cột ngày
    date_col = None
    for candidate in ["time", "date", "trading_date"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError("Cannot find date column. Expected one of: time, date, trading_date")

    # Tự nhận diện cột giá đóng cửa
    close_col = None
    for candidate in ["close", "close_price"]:
        if candidate in df.columns:
            close_col = candidate
            break

    if close_col is None:
        raise ValueError("Cannot find close price column. Expected one of: close, close_price")

    if "volume" not in df.columns:
        raise ValueError("Cannot find volume column.")

        # Clean mixed date formats such as "2026-07-08" and "2026-07-08 00:00:00"
    df[date_col] = (
        df[date_col]
        .astype(str)
        .str.slice(0, 10)
    )

    df[date_col] = pd.to_datetime(
        df[date_col],
        errors="coerce"
    )

    df = df.dropna(subset=[date_col])
    df = df.sort_values(["ticker", date_col])

    all_results = []

    for ticker, group in df.groupby("ticker"):
        g = group.copy()
        g = g.sort_values(date_col)

        g["close_price"] = g[close_col]

        # Moving averages
        g["ma20"] = g["close_price"].rolling(window=20).mean()
        g["ma50"] = g["close_price"].rolling(window=50).mean()
        g["ma200"] = g["close_price"].rolling(window=200).mean()

        # Returns
        g["return_1m"] = g["close_price"].pct_change(periods=21) * 100
        g["return_3m"] = g["close_price"].pct_change(periods=63) * 100
        g["return_6m"] = g["close_price"].pct_change(periods=126) * 100

        # RSI
        g["rsi14"] = calculate_rsi(g["close_price"], window=14)

        # Volatility annualized based on 63 trading days
        g["daily_return"] = g["close_price"].pct_change()
        g["volatility_63d"] = (
            g["daily_return"].rolling(window=63).std() * np.sqrt(252) * 100
        )

        # Price position vs MA
        g["price_above_ma50"] = np.where(g["close_price"] > g["ma50"], 1, 0)
        g["price_above_ma200"] = np.where(g["close_price"] > g["ma200"], 1, 0)

        # Volume trend
        g["volume_avg_20d"] = g["volume"].rolling(window=20).mean()
        g["volume_avg_60d"] = g["volume"].rolling(window=60).mean()
        g["volume_trend"] = np.where(g["volume_avg_20d"] > g["volume_avg_60d"], 1, 0)

        # Quarter
        g["quarter"] = g[date_col].dt.to_period("Q").astype(str)

        # Lấy dòng cuối mỗi quý
        q = (
            g.groupby(["ticker", "quarter"])
            .tail(1)
            [
                [
                    "quarter",
                    "ticker",
                    "close_price",
                    "return_1m",
                    "return_3m",
                    "return_6m",
                    "ma20",
                    "ma50",
                    "ma200",
                    "rsi14",
                    "volatility_63d",
                    "price_above_ma50",
                    "price_above_ma200",
                    "volume_avg_20d",
                    "volume_avg_60d",
                    "volume_trend",
                ]
            ]
        )

        all_results.append(q)

    result = pd.concat(all_results, ignore_index=True)

    # Giữ giai đoạn phân tích chính
    result = result[
        (result["quarter"] >= "2023Q1") &
        (result["quarter"] <= "2026Q3")
    ].copy()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("Saved successfully:")
    print(OUT_FILE)

    print("\nPreview:")
    print(result.head())
    print(result.tail())

    print("\nColumns:")
    print(result.columns)

    print("\nNumber of rows:", len(result))


if __name__ == "__main__":
    main()