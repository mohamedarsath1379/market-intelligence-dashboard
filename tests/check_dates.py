import yfinance as yf

for s in ["^NSEI", "SUNPHARMA.NS"]:
    d = yf.download(s, period="10d", progress=False, auto_adjust=False)
    print(s)
    print(d.tail(5))
    print()