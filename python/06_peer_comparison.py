from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

SIGNAL_FILE = BASE_DIR / "data" / "processed" / "fact_signal_score.csv"
OUT_FILE = BASE_DIR / "data" / "processed" / "fact_peer_comparison.csv"


def classify_opportunity_cost(score_gap: float, return_gap: float) -> str:
    """
    score_gap = peer_score - selected_score
    return_gap = peer_return_3m - selected_return_3m
    """
    if pd.isna(score_gap) or pd.isna(return_gap):
        return "Insufficient Data"

    if score_gap > 20 and return_gap > 5:
        return "High Opportunity Cost"

    if score_gap > 10 or return_gap > 2:
        return "Moderate Opportunity Cost"

    if score_gap > 0:
        return "Low Opportunity Cost"

    return "No Clear Opportunity Cost"


def main():
    df = pd.read_csv(SIGNAL_FILE)

    df.columns = [
        str(col).lower().strip().replace(" ", "_")
        for col in df.columns
    ]

    required_cols = [
        "quarter",
        "ticker",
        "company_name",
        "sector",
        "total_signal_score",
        "quarter_return",
        "return_3m",
        "signal_class",
        "risk_level",
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in fact_signal_score.csv: {missing_cols}")

    rows = []

    for quarter, q_df in df.groupby("quarter"):
        for sector, sector_df in q_df.groupby("sector"):
            sector_df = sector_df.copy()

            # Nếu ngành chỉ có 1 mã trong universe thì không so sánh được
            if len(sector_df) < 2:
                continue

            for _, selected in sector_df.iterrows():
                peers = sector_df[sector_df["ticker"] != selected["ticker"]]

                for _, peer in peers.iterrows():
                    score_gap = peer["total_signal_score"] - selected["total_signal_score"]
                    return_gap = peer["return_3m"] - selected["return_3m"]

                    rows.append(
                        {
                            "quarter": quarter,
                            "selected_ticker": selected["ticker"],
                            "selected_company": selected["company_name"],
                            "selected_sector": selected["sector"],
                            "selected_score": selected["total_signal_score"],
                            "selected_signal_class": selected["signal_class"],
                            "selected_risk_level": selected["risk_level"],
                            "selected_quarter_return": selected["quarter_return"],
                            "selected_return_3m": selected["return_3m"],

                            "peer_ticker": peer["ticker"],
                            "peer_company": peer["company_name"],
                            "peer_score": peer["total_signal_score"],
                            "peer_signal_class": peer["signal_class"],
                            "peer_risk_level": peer["risk_level"],
                            "peer_quarter_return": peer["quarter_return"],
                            "peer_return_3m": peer["return_3m"],

                            "score_gap": score_gap,
                            "return_gap": return_gap,
                            "opportunity_cost_level": classify_opportunity_cost(score_gap, return_gap),
                        }
                    )

    result = pd.DataFrame(rows)

    if result.empty:
        raise ValueError(
            "No peer comparison data created. Check if each sector has at least 2 tickers."
        )

    numeric_cols = result.select_dtypes(include=["float", "int"]).columns
    result[numeric_cols] = result[numeric_cols].round(2)

    result = result.sort_values(
        ["quarter", "selected_ticker", "score_gap"],
        ascending=[True, True, False]
    )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("Saved successfully:")
    print(OUT_FILE)

    print("\nPreview:")
    print(result.head(10))

    print("\nOpportunity cost count:")
    print(result["opportunity_cost_level"].value_counts())

    print("\nNumber of rows:", len(result))


if __name__ == "__main__":
    main()
