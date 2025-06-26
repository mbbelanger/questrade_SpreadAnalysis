import requests
import datetime
import statistics

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def fetch_historical_closes(symbol_id, api_server, access_token, days=50):
    end_time   = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(days=days * 2)

    url = (
        f"{api_server}v1/markets/candles/{symbol_id}"
        f"?startTime={start_time.isoformat()}Z"
        f"&endTime={end_time.isoformat()}Z"
        f"&interval=OneDay"
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    # Optional: print(url)  # for quick debugging
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching candles: {response.text}")

    closes = [c["close"] for c in response.json().get("candles", []) if "close" in c]
    return closes[-days:]


def detect_market_trend(symbol_id, api_server, access_token):
    try:
        closes = fetch_historical_closes(symbol_id, api_server, access_token)

        if len(closes) < 30:
            log(f"⚠️ Not enough data for trend on {symbol_id}")
            return "neutral"

        sma_10 = statistics.mean(closes[-10:])
        sma_30 = statistics.mean(closes[-30:])

        if sma_10 > sma_30 * 1.01:
            return "bullish"
        elif sma_10 < sma_30 * 0.99:
            return "bearish"
        else:
            return "neutral"
    except Exception as e:
        log(f"Error detecting trend: {e}")
        return "neutral"
