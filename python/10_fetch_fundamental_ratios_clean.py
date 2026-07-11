from pathlib import Path
import os
import sys
import time
import io
import contextlib
import logging
import pandas as pd

# Force safer UTF-8 behavior on Windows
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Disable internal logging that may print non-ASCII characters on Windows CMD
logging.disable(logging.CRITICAL)

try:
    from vnstock import Fundamental
except ImportError as exc:
    raise SystemExit(
        "Missing package vnstock. Run:\n"
        ".venv\\Scripts\\python.exe -m pip install -U vnstock pandas"
    ) from exc


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest.csv"
LOG_FILE = BASE_DIR / "data" / "processed" / "fundamental_fetch_log_clean.csv"
BACKUP_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest_backup_before_clean_fetch.csv"

DATA_AS_OF = "2026-07-10"
PRICE_DATE = "2026-07-10"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(col).lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def clean_number(value):
    if pd.isna(value):
        return None

    text = str(value).strip()
    text = text.replace("%", "")
    text = text.replace("x", "")
    text = text.replace("X", "")
    text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def normalize_roe(value):
    number = clean_number(value)

    if number is None:
        return None

    # Convert 0.185 to 18.5 if source returns decimal format
    if -1 <= number <= 1:
        return number * 100

    return number


def fetch_one_ticker(ticker: str):
    """
    Fetch ratio dataframe for one ticker.
    All internal output is redirected to avoid Windows charmap errors.
    """
    sink = io.StringIO()

    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        fun = Fundamental()
        ratio_df = fun.equity(ticker).ratio(period="quarter", orient="time_series")

    if ratio_df is None or ratio_df.empty:
        raise ValueError("No ratio data returned")

    df = ratio_df.copy()

    # Sort by time if a time column exists
    time_col = pick_col(df, ["quarter", "year", "date", "report_date", "period"])
    if time_col:
        try:
            df = df.sort_values(time_col)
        except Exception:
            pass

    latest = df.iloc[-1]

    roe_col = pick_col(df, ["roe", "ROE", "return_on_equity", "roe_pct"])
    pe_col = pick_col(df, ["priceToEarning", "pe_ratio", "pe", "P/E", "p_e"])
    pb_col = pick_col(df, ["priceToBook", "pb_ratio", "pb", "P/B", "p_b"])

    roe = normalize_roe(latest[roe_col]) if roe_col else None
    pe = clean_number(latest[pe_col]) if pe_col else None
    pb = clean_number(latest[pb_col]) if pb_col else None

    return {
        "roe_pct": round(roe, 2) if roe is not None else "",
        "pe": round(pe, 2) if pe is not None else "",
        "pb": round(pb, 2) if pb is not None else "",
        "roe_col": roe_col or "",
        "pe_col": pe_col or "",
        "pb_col": pb_col or "",
    }


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Cannot find input file: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)
    df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")

    logs = []

    print("Starting clean fundamental fetch...")
    print(f"Input file: {INPUT_FILE}")
    print(f"Rows: {len(df)}")
    print("-" * 60)

    for idx, row in df.iterrows():
        ticker = str(row["ticker"]).strip().upper()

        print(f"Fetching {ticker}...")

        try:
            result = fetch_one_ticker(ticker)

            # Only overwrite if vnstock returns a value
            if result["roe_pct"] != "":
                df.loc[idx, "roe_pct"] = result["roe_pct"]
            if result["pe"] != "":
                df.loc[idx, "pe"] = result["pe"]
            if result["pb"] != "":
                df.loc[idx, "pb"] = result["pb"]

            df.loc[idx, "report_period"] = "Latest available"
            df.loc[idx, "metric_basis"] = "Latest available snapshot"
            df.loc[idx, "price_date"] = PRICE_DATE
            df.loc[idx, "data_as_of"] = DATA_AS_OF
            df.loc[idx, "source_name"] = "vnstock"
            df.loc[idx, "source_note"] = (
                "Latest available ratio snapshot collected via vnstock for portfolio project"
            )

            logs.append(
                {
                    "ticker": ticker,
                    "roe_pct": result["roe_pct"],
                    "pe": result["pe"],
                    "pb": result["pb"],
                    "roe_col": result["roe_col"],
                    "pe_col": result["pe_col"],
                    "pb_col": result["pb_col"],
                    "status": "OK",
                    "error": "",
                }
            )

            print(
                f"  OK | ROE={result['roe_pct']} | P/E={result['pe']} | P/B={result['pb']}"
            )

        except Exception as exc:
            logs.append(
                {
                    "ticker": ticker,
                    "roe_pct": "",
                    "pe": "",
                    "pb": "",
                    "roe_col": "",
                    "pe_col": "",
                    "pb_col": "",
                    "status": "FAILED",
                    "error": str(exc),
                }
            )

            print(f"  FAILED | {str(exc)}")

        time.sleep(1)

    log_df = pd.DataFrame(logs)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    log_df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

    ok_count = int((log_df["status"] == "OK").sum())
    failed_count = int((log_df["status"] == "FAILED").sum())

    print("-" * 60)
    print("Done.")
    print(f"Updated file: {OUTPUT_FILE}")
    print(f"Log file: {LOG_FILE}")
    print(f"Backup file: {BACKUP_FILE}")
    print(f"OK: {ok_count}")
    print(f"FAILED: {failed_count}")

    if failed_count > 0:
        print("\nFailed tickers:")
        print(log_df.loc[log_df["status"] == "FAILED", ["ticker", "error"]])


if __name__ == "__main__":
    main()