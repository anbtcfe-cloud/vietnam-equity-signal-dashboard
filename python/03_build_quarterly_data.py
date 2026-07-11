from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

IN_FILE = BASE_DIR / "data" / "processed" / "fact_price_daily.csv"
OUT_FILE = BASE_DIR / "data" / "processed" / "fact_price_quarterly.csv"


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

    # Giữ đúng giai đoạn project MVP
    df = df[
        (df[date_col] >= "2023-01-01") &
        (df[date_col] <= "2026-07-08")
    ].copy()

    # Tạo proxy trading value = close * volume
    df["trading_value"] = df[close_col] * df["volume"]

    # Tạo quý
    df["quarter"] = df[date_col].dt.to_period("Q").astype(str)

    quarterly = (
        df.groupby(["ticker", "quarter"])
        .agg(
            quarter_start_date=(date_col, "first"),
            quarter_end_date=(date_col, "last"),
            quarter_start_price=(close_col, "first"),
            quarter_end_price=(close_col, "last"),
            volume_avg=("volume", "mean"),
            trading_value_avg=("trading_value", "mean"),
            trading_days=(close_col, "count"),
        )
        .reset_index()
    )

    quarterly["quarter_return"] = (
        quarterly["quarter_end_price"] /
        quarterly["quarter_start_price"] - 1
    ) * 100

    # Sắp xếp lại thứ tự cột
    quarterly = quarterly[
        [
            "quarter",
            "ticker",
            "quarter_start_date",
            "quarter_end_date",
            "quarter_start_price",
            "quarter_end_price",
            "quarter_return",
            "volume_avg",
            "trading_value_avg",
            "trading_days",
        ]
    ]

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    quarterly.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("Saved successfully:")
    print(OUT_FILE)
    print("\nPreview:")
    print(quarterly.head())
    print(quarterly.tail())
    print("\nNumber of rows:", len(quarterly))


if __name__ == "__main__":
    main()