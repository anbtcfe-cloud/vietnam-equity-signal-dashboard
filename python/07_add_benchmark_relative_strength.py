from pathlib import Path
from time import sleep
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

SIGNAL_FILE = BASE_DIR / "data" / "processed" / "fact_signal_score.csv"
INDEX_DAILY_FILE = BASE_DIR / "data" / "processed" / "fact_market_index_daily.csv"
INDEX_QUARTERLY_FILE = BASE_DIR / "data" / "processed" / "fact_market_index_quarterly.csv"

START_DATE = "2022-01-01"
END_DATE = "2026-07-08"


def fetch_index(symbol: str, index_code: str) -> pd.DataFrame:
    try:
        from vnstock.api.quote import Quote

        q = Quote(symbol=symbol, source="VCI")
        df = q.history(
            start=START_DATE,
            end=END_DATE,
            interval="1D"
        )

    except Exception:
        from vnstock import Vnstock

        stock = Vnstock().stock(symbol=symbol, source="VCI")
        df = stock.quote.history(
            start=START_DATE,
            end=END_DATE,
            interval="1D"
        )

    df["index_code"] = index_code
    return df


def build_quarterly_index(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        str(col).lower().strip().replace(" ", "_")
        for col in df.columns
    ]

    date_col = None
    for candidate in ["time", "date", "trading_date"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError("Cannot find date column in index data.")

    close_col = None
    for candidate in ["close", "close_price"]:
        if candidate in df.columns:
            close_col = candidate
            break

    if close_col is None:
        raise ValueError("Cannot find close price column in index data.")

    df[date_col] = (
        df[date_col]
        .astype(str)
        .str.slice(0, 10)
    )

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    df = df.sort_values(["index_code", date_col])
    df["quarter"] = df[date_col].dt.to_period("Q").astype(str)

    quarterly = (
        df.groupby(["index_code", "quarter"])
        .agg(
            quarter_start_date=(date_col, "first"),
            quarter_end_date=(date_col, "last"),
            quarter_start_price=(close_col, "first"),
            quarter_end_price=(close_col, "last"),
        )
        .reset_index()
    )

    quarterly["index_quarter_return"] = (
        quarterly["quarter_end_price"] /
        quarterly["quarter_start_price"] - 1
    ) * 100

    return quarterly


def relative_strength_score(x: float) -> int:
    if pd.isna(x):
        return 50
    if x >= 10:
        return 100
    if x >= 5:
        return 80
    if x >= 0:
        return 60
    if x >= -5:
        return 40
    return 20


def classify_signal(score: float) -> str:
    if pd.isna(score):
        return "Insufficient Data"
    if score >= 80:
        return "Strong Watchlist"
    if score >= 65:
        return "Positive Signal"
    if score >= 50:
        return "Neutral"
    if score >= 35:
        return "Weak Signal"
    return "Risk Alert"


def main():
    print("Fetching market benchmark data...")

    all_index_data = []

    # Start with VNINDEX first. VN30 may depend on source availability.
    index_symbols = [
        ("VNINDEX", "VNINDEX"),
        ("VN30", "VN30"),
    ]

    for symbol, index_code in index_symbols:
        try:
            print(f"Fetching {index_code}...")
            df = fetch_index(symbol, index_code)

            if df.empty:
                print(f"No data for {index_code}")
                continue

            all_index_data.append(df)
            sleep(3)

        except BaseException as e:
            print(f"Failed to fetch {index_code}: {e}")
            continue

    if not all_index_data:
        raise ValueError("No market index data fetched.")

    index_daily = pd.concat(all_index_data, ignore_index=True)
    index_daily.to_csv(INDEX_DAILY_FILE, index=False, encoding="utf-8-sig")

    index_quarterly = build_quarterly_index(index_daily)
    index_quarterly.to_csv(INDEX_QUARTERLY_FILE, index=False, encoding="utf-8-sig")

    print("Market index quarterly data saved:")
    print(INDEX_QUARTERLY_FILE)

    signal = pd.read_csv(SIGNAL_FILE)

    # Backup old score before overwriting
    if "base_total_signal_score" not in signal.columns:
        signal["base_total_signal_score"] = signal["total_signal_score"]

    if "base_signal_class" not in signal.columns:
        signal["base_signal_class"] = signal["signal_class"]

    benchmark = (
        index_quarterly
        .pivot_table(
            index="quarter",
            columns="index_code",
            values="index_quarter_return",
            aggfunc="first"
        )
        .reset_index()
    )

    if "VNINDEX" in benchmark.columns:
        benchmark = benchmark.rename(columns={"VNINDEX": "vnindex_return"})

    if "VN30" in benchmark.columns:
        benchmark = benchmark.rename(columns={"VN30": "vn30_return"})

    # Remove old benchmark columns if rerunning
    for col in [
        "vnindex_return",
        "vn30_return",
        "relative_strength_vs_vnindex",
        "relative_strength_vs_vn30",
        "relative_strength_score",
    ]:
        if col in signal.columns:
            signal = signal.drop(columns=[col])

    signal = signal.merge(
        benchmark,
        on="quarter",
        how="left"
    )

    if "vnindex_return" in signal.columns:
        signal["relative_strength_vs_vnindex"] = (
            signal["quarter_return"] - signal["vnindex_return"]
        )
    else:
        signal["relative_strength_vs_vnindex"] = np.nan

    if "vn30_return" in signal.columns:
        signal["relative_strength_vs_vn30"] = (
            signal["quarter_return"] - signal["vn30_return"]
        )
    else:
        signal["relative_strength_vs_vn30"] = np.nan

    signal["relative_strength_score"] = signal["relative_strength_vs_vnindex"].apply(
        relative_strength_score
    )

    # New score model for Phase 2
    signal["total_signal_score"] = (
        signal["technical_score"] * 0.25
        + signal["fundamental_score"] * 0.25
        + signal["valuation_score"] * 0.15
        + signal["liquidity_score"] * 0.15
        + signal["risk_score"] * 0.10
        + signal["relative_strength_score"] * 0.10
    )

    signal["signal_class"] = signal["total_signal_score"].apply(classify_signal)

    numeric_cols = signal.select_dtypes(include=["float", "int"]).columns
    signal[numeric_cols] = signal[numeric_cols].round(2)

    signal.to_csv(SIGNAL_FILE, index=False, encoding="utf-8-sig")

    print("Updated fact_signal_score with benchmark and relative strength.")
    print("Rows:", len(signal))
    print("Tickers:", signal["ticker"].nunique())

    print("\nPreview:")
    print(
        signal[
            [
                "quarter",
                "ticker",
                "quarter_return",
                "vnindex_return",
                "relative_strength_vs_vnindex",
                "relative_strength_score",
                "total_signal_score",
                "signal_class",
            ]
        ].head(10)
    )


if __name__ == "__main__":
    main()