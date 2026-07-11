from pathlib import Path
import os
import sys
import time
import io
import contextlib
import logging
import pandas as pd

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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
LOG_FILE = BASE_DIR / "data" / "processed" / "fundamental_fetch_log_resume.csv"
BACKUP_FILE = BASE_DIR / "data" / "processed" / "fact_fundamental_latest_backup_before_resume.csv"

DATA_AS_OF = "2026-07-10"
PRICE_DATE = "2026-07-10"

SLEEP_SECONDS = 7
RATE_LIMIT_WAIT_SECONDS = 75
MAX_RETRIES = 3


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

    if -1 <= number <= 1:
        return number * 100

    return number


def has_all_three_values(row) -> bool:
    for col in ["roe_pct", "pe", "pb"]:
        value = row.get(col, "")
        if pd.isna(value) or str(value).strip() == "":
            return False
    return True


def fetch_one_ticker(ticker: str):
    sink = io.StringIO()

    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        fun = Fundamental()
        ratio_df = fun.equity(ticker).ratio(period="quarter", orient="time_series")

    if ratio_df is None or ratio_df.empty:
        raise ValueError("No ratio data returned")

    df = ratio_df.copy()

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

    print("Starting resume slow fundamental fetch...")
    print(f"Rows: {len(df)}")
    print(f"Sleep per ticker: {SLEEP_SECONDS} seconds")
    print("-" * 60)

    for idx, row in df.iterrows():
        ticker = str(row["ticker"]).strip().upper()

        if has_all_three_values(row):
            print(f"Skipping {ticker}: already has ROE/P/E/P/B")
            logs.append({
                "ticker": ticker,
                "roe_pct": row.get("roe_pct", ""),
                "pe": row.get("pe", ""),
                "pb": row.get("pb", ""),
                "status": "SKIPPED_EXISTING",
                "error": "",
            })
            continue

        print(f"Fetching {ticker}...")

        success = False
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = fetch_one_ticker(ticker)

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

                df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

                logs.append({
                    "ticker": ticker,
                    "roe_pct": result["roe_pct"],
                    "pe": result["pe"],
                    "pb": result["pb"],
                    "status": "OK",
                    "error": "",
                })

                print(
                    f"  OK | ROE={result['roe_pct']} | "
                    f"P/E={result['pe']} | P/B={result['pb']}"
                )

                success = True
                break

            except BaseException as exc:
                last_error = str(exc)
                print(f"  Attempt {attempt} failed | {last_error}")

                if "Rate Limit" in last_error or "rate" in last_error.lower() or "giới hạn" in last_error.lower():
                    print(f"  Rate limit detected. Waiting {RATE_LIMIT_WAIT_SECONDS} seconds...")
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                else:
                    time.sleep(5)

        if not success:
            logs.append({
                "ticker": ticker,
                "roe_pct": "",
                "pe": "",
                "pb": "",
                "status": "FAILED",
                "error": last_error,
            })

        pd.DataFrame(logs).to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

        print(f"Waiting {SLEEP_SECONDS} seconds before next ticker...")
        time.sleep(SLEEP_SECONDS)

    log_df = pd.DataFrame(logs)
    log_df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print("-" * 60)
    print("Done.")
    print(f"Updated file: {OUTPUT_FILE}")
    print(f"Log file: {LOG_FILE}")

    print("Status counts:")
    print(log_df["status"].value_counts())


if __name__ == "__main__":
    main()