from pathlib import Path
from time import sleep
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

TICKER_FILE = BASE_DIR / "data" / "mapping" / "dim_ticker.csv"
OUT_FILE = BASE_DIR / "data" / "processed" / "fact_price_daily.csv"


START_DATE = "2022-01-01"
END_DATE = "2026-07-08"

REQUEST_DELAY_SECONDS = 5
RATE_LIMIT_WAIT_SECONDS = 70


def load_tickers() -> list[str]:
    tickers = pd.read_csv(TICKER_FILE)
    return (
        tickers["ticker"]
        .dropna()
        .astype(str)
        .str.upper()
        .str.strip()
        .unique()
        .tolist()
    )


def load_existing_data() -> pd.DataFrame:
    if OUT_FILE.exists():
        try:
            existing = pd.read_csv(OUT_FILE)
            existing.columns = [
                str(col).lower().strip().replace(" ", "_")
                for col in existing.columns
            ]

            if "ticker" in existing.columns:
                existing["ticker"] = existing["ticker"].astype(str).str.upper().str.strip()

            print(f"Existing file found: {OUT_FILE}")
            print(f"Existing rows: {len(existing)}")
            return existing

        except Exception as e:
            print(f"Cannot read existing file, will fetch from scratch: {e}")

    return pd.DataFrame()


def fetch_price(symbol: str, start: str, end: str) -> pd.DataFrame:
    try:
        from vnstock.api.quote import Quote

        q = Quote(symbol=symbol, source="VCI")
        df = q.history(
            start=start,
            end=end,
            interval="1D"
        )

    except Exception:
        from vnstock import Vnstock

        stock = Vnstock().stock(symbol=symbol, source="VCI")
        df = stock.quote.history(
            start=start,
            end=end,
            interval="1D"
        )

    df["ticker"] = symbol
    return df


def main():
    tickers = load_tickers()
    existing = load_existing_data()

    existing_tickers = set()
    if not existing.empty and "ticker" in existing.columns:
        existing_tickers = set(existing["ticker"].dropna().astype(str).str.upper().unique())

    all_data = []

    if not existing.empty:
        all_data.append(existing)

    print(f"\nTotal tickers in universe: {len(tickers)}")
    print(f"Tickers already in existing file: {len(existing_tickers)}")

    missing_tickers = [ticker for ticker in tickers if ticker not in existing_tickers]

    print(f"Tickers to fetch now: {len(missing_tickers)}")
    print(missing_tickers)

    for ticker in missing_tickers:
        success = False

        for attempt in range(1, 3):
            try:
                print(f"\nFetching {ticker} | Attempt {attempt}/2...")
                df = fetch_price(ticker, START_DATE, END_DATE)

                if df.empty:
                    print(f"No data returned for {ticker}")
                    break

                df.columns = [
                    str(col).lower().strip().replace(" ", "_")
                    for col in df.columns
                ]

                all_data.append(df)
                success = True

                print(f"Fetched {ticker}: {len(df)} rows")
                sleep(REQUEST_DELAY_SECONDS)
                break

            except BaseException as e:
                print(f"Failed to fetch {ticker}: {e}")

                if attempt == 1:
                    print(f"Waiting {RATE_LIMIT_WAIT_SECONDS} seconds before retry...")
                    sleep(RATE_LIMIT_WAIT_SECONDS)
                else:
                    print(f"Skipped {ticker} after 2 failed attempts.")

        if not success:
            continue

    if not all_data:
        raise ValueError("No data available. Please check ticker list or vnstock connection.")

    result = pd.concat(all_data, ignore_index=True)

    result.columns = [
        str(col).lower().strip().replace(" ", "_")
        for col in result.columns
    ]

    if "ticker" in result.columns:
        result["ticker"] = result["ticker"].astype(str).str.upper().str.strip()

    result = result.drop_duplicates()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("\nSaved successfully:")
    print(OUT_FILE)
    print("\nNumber of rows:", len(result))

    if "ticker" in result.columns:
        print("\nNumber of tickers in output:", result["ticker"].nunique())
        print(sorted(result["ticker"].dropna().unique()))


if __name__ == "__main__":
    main()