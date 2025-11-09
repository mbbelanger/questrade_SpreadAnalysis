"""
Test the Greeks API endpoint with detailed response inspection
"""
import requests
import json
from questrade_utils import refresh_access_token, get_headers, search_symbol
import questrade_utils

print("=" * 70)
print("QUESTRADE GREEKS API TEST")
print("=" * 70)

# Refresh token
refresh_access_token()
print(f"\nAPI Server: {questrade_utils.API_SERVER}")

# Search for QQQ
print("\n1. Searching for QQQ symbol...")
symbol_data = search_symbol("QQQ")
if not symbol_data:
    print("ERROR: Could not find QQQ")
    exit(1)

symbol_id = symbol_data['symbolId']
print(f"   Symbol ID: {symbol_id}")

# Get option chain
print("\n2. Fetching option chain...")
chain_url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
chain_resp = requests.get(chain_url, headers=get_headers())

print(f"   Status Code: {chain_resp.status_code}")

if chain_resp.status_code != 200:
    print(f"   ERROR: {chain_resp.text}")
    exit(1)

chain_data = chain_resp.json()
option_chain = chain_data.get("optionChain", [])

print(f"   Found {len(option_chain)} expiration dates")

if not option_chain:
    print("   ERROR: No option chain data")
    exit(1)

# Get first expiry details
first_expiry = option_chain[0]
expiry_date = first_expiry.get("expiryDate", "").split("T")[0]
print(f"   First expiry: {expiry_date}")

# Get first few option IDs
option_ids = []
chain_roots = first_expiry.get("chainPerRoot", [])

if chain_roots:
    strikes = chain_roots[0].get("chainPerStrikePrice", [])[:3]

    print(f"\n3. Collecting option IDs from first {len(strikes)} strikes:")
    for strike in strikes:
        strike_price = strike.get("strikePrice")
        call_id = strike.get("callSymbolId")
        put_id = strike.get("putSymbolId")

        print(f"   Strike {strike_price}: Call={call_id}, Put={put_id}")

        if call_id:
            option_ids.append(str(call_id))
        if put_id:
            option_ids.append(str(put_id))

if not option_ids:
    print("   ERROR: No option IDs collected")
    exit(1)

print(f"\n   Collected {len(option_ids)} option IDs: {option_ids[:5]}")

# Test Greeks API
print(f"\n4. Fetching Greeks for {len(option_ids)} options...")
greeks_url = f"{questrade_utils.API_SERVER}v1/markets/quotes/options"
print(f"   URL: {greeks_url}")

# Correct endpoint uses POST with optionIds in request body
payload = {"optionIds": [int(id) for id in option_ids]}
print(f"   Payload: {payload}")

greeks_resp = requests.post(greeks_url, json=payload, headers=get_headers(), timeout=10)
print(f"   Status Code: {greeks_resp.status_code}")

if greeks_resp.status_code != 200:
    print(f"   ERROR Response:")
    print(f"   {greeks_resp.text}")
    exit(1)

greeks_data = greeks_resp.json()

# Print raw response structure
print(f"\n5. Greeks API Response Structure:")
print(f"   Response keys: {list(greeks_data.keys())}")

option_greeks = greeks_data.get("optionQuotes", [])
print(f"   Number of option quotes: {len(option_greeks)}")

if option_greeks:
    print(f"\n6. Sample Greeks Data (first 3 options):")
    for i, greek in enumerate(option_greeks[:3], 1):
        print(f"\n   Option {i}:")
        print(f"      symbolId: {greek.get('symbolId')}")
        print(f"      volatility: {greek.get('volatility')}")
        print(f"      delta: {greek.get('delta')}")
        print(f"      gamma: {greek.get('gamma')}")
        print(f"      theta: {greek.get('theta')}")
        print(f"      vega: {greek.get('vega')}")
        print(f"      rho: {greek.get('rho')}")
        print(f"      Raw data: {json.dumps(greek, indent=10)}")

    # Check if all volatilities are 0
    volatilities = [g.get('volatility', 0) for g in option_greeks]
    non_zero_vols = [v for v in volatilities if v and v > 0]

    print(f"\n7. Volatility Analysis:")
    print(f"   Total volatility values: {len(volatilities)}")
    print(f"   Non-zero volatilities: {len(non_zero_vols)}")
    print(f"   Sample volatilities: {volatilities[:10]}")

    if not non_zero_vols:
        print("\n   [!] ALL VOLATILITIES ARE ZERO OR NULL")
        print("\n   Possible reasons:")
        print("   1. Market is closed (Greeks may only update during market hours)")
        print("   2. Account doesn't have real-time Greeks access")
        print("   3. Questrade API limitation")
        print("\n   RECOMMENDATION: Re-run this script during market hours")
        print("   (9:30 AM - 4:00 PM ET, Monday-Friday)")
    else:
        print(f"\n   [OK] Found {len(non_zero_vols)} valid IV values")
        print(f"   IV range: {min(non_zero_vols):.4f} - {max(non_zero_vols):.4f}")
else:
    print("\n   [!] NO GREEKS DATA RETURNED")
    print("   The API returned an empty optionGreeks array")

print("\n" + "=" * 70)
