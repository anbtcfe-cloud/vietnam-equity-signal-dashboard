from pathlib import Path
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

TECH_FILE = BASE_DIR / "data" / "processed" / "fact_technical_indicators.csv"
PRICE_Q_FILE = BASE_DIR / "data" / "processed" / "fact_price_quarterly.csv"
TICKER_FILE = BASE_DIR / "data" / "mapping" / "dim_ticker.csv"

OUT_FILE = BASE_DIR / "data" / "processed" / "fact_signal_score.csv"


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


def classify_risk(volatility: float, median_volatility: float) -> str:
    if pd.isna(volatility):
        return "Unknown"
    if volatility <= median_volatility * 0.8:
        return "Low Risk"
    if volatility <= median_volatility * 1.2:
        return "Medium Risk"
    return "High Risk"


def main():
    tech = pd.read_csv(TECH_FILE)
    price_q = pd.read_csv(PRICE_Q_FILE)
    tickers = pd.read_csv(TICKER_FILE)

    # Chuẩn hóa tên cột
    for df in [tech, price_q, tickers]:
        df.columns = [
            str(col).lower().strip().replace(" ", "_")
            for col in df.columns
        ]

    # Merge technical + price quarterly
    df = tech.merge(
        price_q[
            [
                "quarter",
                "ticker",
                "quarter_return",
                "volume_avg",
                "trading_value_avg",
                "trading_days",
            ]
        ],
        on=["quarter", "ticker"],
        how="left",
    )

    # Merge ticker info
    df = df.merge(
        tickers[
            [
                "ticker",
                "company_name",
                "exchange",
                "sector",
                "industry",
                "is_vn30",
            ]
        ],
        on="ticker",
        how="left",
    )

    # =========================
    # 1. TECHNICAL SCORE
    # =========================
    # Thang điểm 0–100

    df["technical_score"] = 0

    # Momentum
    df["technical_score"] += np.where(df["return_1m"] > 0, 10, 0)
    df["technical_score"] += np.where(df["return_3m"] > 0, 15, 0)
    df["technical_score"] += np.where(df["return_6m"] > 0, 15, 0)

    # Moving average trend
    df["technical_score"] += np.where(df["price_above_ma50"] == 1, 15, 0)
    df["technical_score"] += np.where(df["price_above_ma200"] == 1, 20, 0)

    # RSI healthy zone
    df["technical_score"] += np.where(df["rsi14"].between(50, 70), 15, 0)

    # Volume confirmation
    df["technical_score"] += np.where(df["volume_trend"] == 1, 10, 0)

    # =========================
    # 2. LIQUIDITY SCORE
    # =========================
    # Trading value percentile theo từng quý
    df["liquidity_score"] = (
        df.groupby("quarter")["trading_value_avg"]
        .rank(pct=True)
        * 100
    )

    # =========================
    # 3. RISK SCORE
    # =========================
    # Volatility càng thấp thì risk score càng cao
    df["risk_score"] = (
        df.groupby("quarter")["volatility_63d"]
        .rank(pct=True, ascending=False)
        * 100
    )

    # =========================
    # 4. FUNDAMENTAL & VALUATION PLACEHOLDER
    # =========================
    # MVP hiện tại chưa nhập ROE, P/E, P/B, tăng trưởng lợi nhuận.
    # Tạm để 50 để scoring chạy được.
    # Sau này mình sẽ thay bằng dữ liệu thật.
    df["fundamental_score"] = 50
    df["valuation_score"] = 50

    # =========================
    # 5. TOTAL SIGNAL SCORE
    # =========================
    df["total_signal_score"] = (
        df["technical_score"] * 0.30
        + df["fundamental_score"] * 0.25
        + df["valuation_score"] * 0.20
        + df["liquidity_score"] * 0.15
        + df["risk_score"] * 0.10
    )

    df["signal_class"] = df["total_signal_score"].apply(classify_signal)

    # Risk level theo median volatility từng quý
    quarter_median_vol = (
        df.groupby("quarter")["volatility_63d"]
        .median()
        .rename("quarter_median_volatility")
        .reset_index()
    )

    df = df.merge(quarter_median_vol, on="quarter", how="left")

    df["risk_level"] = df.apply(
        lambda row: classify_risk(
            row["volatility_63d"],
            row["quarter_median_volatility"]
        ),
        axis=1,
    )

    # Sắp xếp cột output
    output_cols = [
        "quarter",
        "ticker",
        "company_name",
        "exchange",
        "sector",
        "industry",
        "is_vn30",
        "close_price",
        "quarter_return",
        "return_1m",
        "return_3m",
        "return_6m",
        "rsi14",
        "volatility_63d",
        "volume_avg",
        "trading_value_avg",
        "technical_score",
        "fundamental_score",
        "valuation_score",
        "liquidity_score",
        "risk_score",
        "total_signal_score",
        "signal_class",
        "risk_level",
    ]

    result = df[output_cols].copy()

    # Làm tròn số để dễ đọc trong Excel/Power BI
    numeric_cols = result.select_dtypes(include=["float", "int"]).columns
    result[numeric_cols] = result[numeric_cols].round(2)

    result = result.sort_values(
        ["quarter", "total_signal_score"],
        ascending=[True, False]
    )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("Saved successfully:")
    print(OUT_FILE)

    print("\nPreview:")
    print(result.head(10))

    print("\nSignal class count:")
    print(result["signal_class"].value_counts())

    print("\nNumber of rows:", len(result))


if __name__ == "__main__":
    main()
