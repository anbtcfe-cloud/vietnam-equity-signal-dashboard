from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_FILE = BASE_DIR / "data" / "mapping" / "dim_ticker.csv"


VN30_UNIVERSE = [
    # Banking
    {"ticker": "VCB", "company_name": "Vietcombank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "BID", "company_name": "BIDV", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "CTG", "company_name": "VietinBank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "TCB", "company_name": "Techcombank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "MBB", "company_name": "Military Bank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "VPB", "company_name": "VPBank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "ACB", "company_name": "ACB", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "STB", "company_name": "Sacombank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "HDB", "company_name": "HDBank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},
    {"ticker": "TPB", "company_name": "TPBank", "exchange": "HOSE", "sector": "Banking", "industry": "Commercial Bank", "is_vn30": 1},

    # Securities
    {"ticker": "SSI", "company_name": "SSI Securities", "exchange": "HOSE", "sector": "Securities", "industry": "Brokerage", "is_vn30": 1},
    {"ticker": "HCM", "company_name": "HSC Securities", "exchange": "HOSE", "sector": "Securities", "industry": "Brokerage", "is_vn30": 1},
    {"ticker": "VCI", "company_name": "Vietcap Securities", "exchange": "HOSE", "sector": "Securities", "industry": "Brokerage", "is_vn30": 1},

    # Real Estate
    {"ticker": "VIC", "company_name": "Vingroup", "exchange": "HOSE", "sector": "Real Estate", "industry": "Conglomerate / Real Estate", "is_vn30": 1},
    {"ticker": "VHM", "company_name": "Vinhomes", "exchange": "HOSE", "sector": "Real Estate", "industry": "Residential Real Estate", "is_vn30": 1},
    {"ticker": "VRE", "company_name": "Vincom Retail", "exchange": "HOSE", "sector": "Real Estate", "industry": "Retail Real Estate", "is_vn30": 1},
    {"ticker": "KDH", "company_name": "Khang Dien House", "exchange": "HOSE", "sector": "Real Estate", "industry": "Residential Real Estate", "is_vn30": 1},

    # Consumer / Retail
    {"ticker": "MWG", "company_name": "Mobile World", "exchange": "HOSE", "sector": "Retail", "industry": "Consumer Retail", "is_vn30": 1},
    {"ticker": "PNJ", "company_name": "Phu Nhuan Jewelry", "exchange": "HOSE", "sector": "Retail", "industry": "Jewelry Retail", "is_vn30": 1},
    {"ticker": "MSN", "company_name": "Masan Group", "exchange": "HOSE", "sector": "Consumer", "industry": "Consumer Goods", "is_vn30": 1},
    {"ticker": "VNM", "company_name": "Vinamilk", "exchange": "HOSE", "sector": "Consumer", "industry": "Dairy", "is_vn30": 1},
    {"ticker": "SAB", "company_name": "Sabeco", "exchange": "HOSE", "sector": "Consumer", "industry": "Beverage", "is_vn30": 1},

    # Technology
    {"ticker": "FPT", "company_name": "FPT Corporation", "exchange": "HOSE", "sector": "Technology", "industry": "IT Services", "is_vn30": 1},

    # Materials / Industrials
    {"ticker": "HPG", "company_name": "Hoa Phat Group", "exchange": "HOSE", "sector": "Steel", "industry": "Steel", "is_vn30": 1},
    {"ticker": "GVR", "company_name": "Vietnam Rubber Group", "exchange": "HOSE", "sector": "Materials", "industry": "Rubber / Industrial Materials", "is_vn30": 1},

    # Energy / Utilities
    {"ticker": "GAS", "company_name": "PV Gas", "exchange": "HOSE", "sector": "Energy", "industry": "Gas", "is_vn30": 1},
    {"ticker": "PLX", "company_name": "Petrolimex", "exchange": "HOSE", "sector": "Energy", "industry": "Petroleum Distribution", "is_vn30": 1},
    {"ticker": "POW", "company_name": "PV Power", "exchange": "HOSE", "sector": "Utilities", "industry": "Power Generation", "is_vn30": 1},

    # Transportation / Aviation
    {"ticker": "VJC", "company_name": "Vietjet Air", "exchange": "HOSE", "sector": "Transportation", "industry": "Airlines", "is_vn30": 1},

    # Other large-cap candidate
    {"ticker": "BCM", "company_name": "Becamex IDC", "exchange": "HOSE", "sector": "Industrial Parks", "industry": "Industrial Real Estate", "is_vn30": 1},
]


def main():
    df = pd.DataFrame(VN30_UNIVERSE)

    df["ticker"] = df["ticker"].str.upper().str.strip()

    # Kiểm tra trùng mã
    duplicates = df[df["ticker"].duplicated()]
    if not duplicates.empty:
        raise ValueError(f"Duplicate tickers found: {duplicates['ticker'].tolist()}")

    # Kiểm tra đủ 30 mã
    if len(df) != 30:
        raise ValueError(f"Expected 30 tickers, but got {len(df)}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print("VN30 universe saved successfully:")
    print(OUT_FILE)
    print()
    print(df[["ticker", "company_name", "sector"]])
    print()
    print("Number of tickers:", len(df))


if __name__ == "__main__":
    main()