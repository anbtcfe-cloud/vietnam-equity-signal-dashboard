from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

DIM_FILE = BASE_DIR / "data" / "mapping" / "dim_ticker.csv"
OUT_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest.csv"

def main():
    dim = pd.read_csv(DIM_FILE)

    df = dim[["ticker", "company_name", "sector"]].copy()

    df["report_period"] = "Latest available"
    df["metric_basis"] = "Latest available snapshot"
    df["price_date"] = "2026-07-10"
    df["data_as_of"] = "2026-07-10"

    df["roe_pct"] = ""
    df["pe"] = ""
    df["pb"] = ""

    df["source_name"] = "Manual input"
    df["source_note"] = "Snapshot data for portfolio project"

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("Created fundamental template:")
    print(OUT_FILE)
    print("Rows:", len(df))
    print(df.head())

if __name__ == "__main__":
    main()