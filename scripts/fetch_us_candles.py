import requests, json, os, time
from datetime import datetime, timedelta

STOCKS = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMD","AVGO","TSM",
    "PLTR","ARM","SMCI","XOM","CVX","COP","NEE",
    "BRK-B","JPM","V","MA","AMZN","COST","NKE",
    "LLY","JNJ","UNH","LMT","RTX",
    "SPY","QQQ","GLD",
    "TSLA","RKLB","LUNR","ASTS","ARKX"
]

def fetch_candle(sym, token):
    frm = int((datetime.now() - timedelta(days=120)).timestamp())
    to = int(datetime.now().timestamp())
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": sym, "resolution": "D", "from": frm, "to": to, "token": token}
    try:
        r = requests.get(url, params=params, timeout=15)
        d = r.json()
        if d.get("s") == "ok" and d.get("t"):
            result = []
            for i, t in enumerate(d["t"]):
                result.append({
                    "date": datetime.fromtimestamp(t).strftime("%Y-%m-%d"),
                    "open": d["o"][i],
                    "high": d["h"][i],
                    "low": d["l"][i],
                    "close": d["c"][i],
                    "volume": d["v"][i]
                })
            return result
    except Exception as e:
        print(f"  Error {sym}: {e}")
    return []

def main():
    token = os.environ.get("FINNHUB_KEY", "d85n131r01qitd92qs00d85n131r01qitd92qs0g")
    os.makedirs("data/us_candles", exist_ok=True)
    results = {}
    for sym in STOCKS:
        print(f"抓取 {sym}...")
        candles = fetch_candle(sym, token)
        if candles:
            path = f"data/us_candles/{sym}.json"
            with open(path, "w") as f:
                json.dump({"sym": sym, "candles": candles, "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}, f)
            results[sym] = len(candles)
            print(f"  OK {len(candles)} 筆")
        else:
            print(f"  SKIP {sym}")
        time.sleep(1.2)
    with open("data/us_candles/index.json", "w") as f:
        json.dump({"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "stocks": list(results.keys())}, f, indent=2)
    print(f"完成！共 {len(results)} 支")

if __name__ == "__main__":
    main()
