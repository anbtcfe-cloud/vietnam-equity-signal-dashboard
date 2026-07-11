from vnstock import Vnstock

symbol = "VCB"

stock = Vnstock().stock(symbol=symbol, source="VCI")

df = stock.quote.history(
    start="2023-01-01",
    end="2026-07-08",
    interval="1D"
)

print("VNStock is working")
print(df.head())
print(df.tail())
print(df.columns)
print("Number of rows:", len(df))