from pathlib import Path
import time
import sys
import io
import contextlib
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from vnstock import Fundamental
except ImportError as exc:
    raise SystemExit(
        "Missing package vnstock. Run this command first:\n"
        ".venv\\Scripts\\python.exe -m pip install -U vnstock pandas"
    ) from exc


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest.csv"
BACKUP_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest_backup_before_fetch.csv"
LOG_FILE = BASE_DIR / "data" / "processed" / "fundamental_fetch_log.csv"

DATA_AS_OF = "2026-07-10"
PRICE_DATE = "2026-07-10"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(c).lower(): c for c in df.columns}

    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

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

    if -1 <= number <= 1:
        return number * 100

    return number


def get_latest_ratio_row(ticker: str):
    fun = Fundamental()

    # Suppress vnstock internal output to avoid Windows charmap encoding errors
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        ratio_df = fun.equity(ticker).ratio(period="quarter", orient="time_series")

    if ratio_df is None or ratio_df.empty:
        return None, None

    df = ratio_df.copy()

    time_col = pick_col(df, ["quarter", "year", "date", "report_date", "period"])
    if time_col:
        try:
            df = df.sort_values(time_col)
        except Exception:
            pass

    latest = df.iloc[-1]
    return df, latest


def extract_ratios(ratio_df: pd.DataFrame, latest_row: pd.Series):
    roe_col = pick_col(
        ratio_df,
        [
            "roe",
            "return_on_equity",
            "roe_pct",
            "ROE",
        ],
    )

    pe_col = pick_col(
        ratio_df,
        [
            "pe_ratio",
            "priceToEarning",
            "pe",
            "p_e",
            "P/E",
        ],
    )

    pb_col = pick_col(
        ratio_df,
        [
            "pb_ratio",
            "priceToBook",
            "pb",
            "p_b",
            "P/B",
        ],
    )

    roe = normalize_roe(latest_row[roe_col]) if roe_col else None
    pe = clean_number(latest_row[pe_col]) if pe_col else None
    pb = clean_number(latest_row[pb_col]) if pb_col else None

    return roe, pe, pb, roe_col, pe_col, pb_col


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Cannot find input file: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)
    df.to_csv(BACKUP_FILE, index=False, encoding="utf-8-sig")

    logs = []

    print("Starting fundamental ratio fetch...")
    print(f"Input file: {INPUT_FILE}")
    print(f"Rows: {len(df)}")
    print("-" * 60)

    for i, row in df.iterrows():
        ticker = str(row["ticker"]).strip().upper()
        print(f"Fetching {ticker}...")

        try:
            ratio_df, latest = get_latest_ratio_row(ticker)

            if latest is None:
                raise ValueError("No ratio data returned")

            roe, pe, pb, roe_col, pe_col, pb_col = extract_ratios(ratio_df, latest)

            df.loc[i, "roe_pct"] = round(roe, 2) if roe is not None else ""
            df.loc[i, "pe"] = round(pe, 2) if pe is not None else ""
            df.loc[i, "pb"] = round(pb, 2) if pb is not None else ""

            df.loc[i, "report_period"] = "Latest available"
            df.loc[i, "metric_basis"] = "Latest available snapshot"
            df.loc[i, "price_date"] = PRICE_DATE
            df.loc[i, "data_as_of"] = DATA_AS_OF
            df.loc[i, "source_name"] = "vnstock"
            df.loc[i, "source_note"] = "Latest available ratio snapshot collected via vnstock for portfolio project"

            logs.append(
                {
                    "ticker": ticker,
                    "roe_pct": round(roe, 2) if roe is not None else "",
                    "pe": round(pe, 2) if pe is not None else "",
                    "pb": round(pb, 2) if pb is not None else "",
                    "roe_col": roe_col or "",
                    "pe_col": pe_col or "",
                    "pb_col": pb_col or "",
                    "status": "OK",
                    "error": "",
                }
            )

            print(
                f"  OK | ROE={round(roe, 2) if roe is not None else ''} "
                f"| P/E={round(pe, 2) if pe is not None else ''} "
                f"| P/B={round(pb, 2) if pb is not None else ''}"
            )

        except Exception as e:
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
                    "error": str(e),
                }
            )

            print(f"  FAILED | {e}")

        time.sleep(1)

    log_df = pd.DataFrame(logs)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    log_df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

    print("-" * 60)
    print("Done.")
    print(f"Updated file: {OUTPUT_FILE}")
    print(f"Backup file: {BACKUP_FILE}")
    print(f"Log file: {LOG_FILE}")

    ok_count = (log_df["status"] == "OK").sum()
    fail_count = (log_df["status"] == "FAILED").sum()

    print(f"OK: {ok_count}")
    print(f"FAILED: {fail_count}")

    if fail_count > 0:
        print("\nFailed tickers:")
        print(log_df.loc[log_df["status"] == "FAILED", ["ticker", "error"]])


if __name__ == "__main__":
    main()