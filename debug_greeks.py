"""
Debug script to check what the Questrade Greeks API is returning
"""
import requests
from questrade_utils import refresh_access_token, get_headers, search_symbol
import questrade_utils

# Refresh token and get API server
refresh_access_token()

# Search for QQQ
symbol_data = search_symbol("QQQ")
if not symbol_data:
    print("ERROR: Could not find QQQ symbol")
    exit(1)

symbol_id = symbol_data['symbolId']
print(f"\nQQQ Symbol ID: {symbol_id}")

# Get option chain
print(f"\nFetching option chain...")
chain_url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
chain_resp = requests.get(chain_url, headers=get_headers()).json()

# Get first few option IDs
option_ids = []
option_chain = chain_resp.get("optionChain", [])

if option_chain:
    first_expiry = option_chain[0]
    print(f"First expiry: {first_expiry.get('expiryDate')}")

    chain_roots = first_expiry.get("chainPerRoot", [])
    if chain_roots:
        strikes = chain_roots[0].get("chainPerStrikePrice", [])[:3]  # First 3 strikes

        for strike in strikes:
            call_id = strike.get("callSymbolId")
            if call_id:
                option_ids.append(str(call_id))
                print(f"  Strike {strike.get('strikePrice')}: Call ID = {call_id}")

if not option_ids:
    print("ERROR: No option IDs found")
    exit(1)

# Fetch Greeks for these options
print(f"\nFetching Greeks for {len(option_ids)} option(s)...")
greeks_url = f"{questrade_utils.API_SERVER}v1/markets/options/greeks?optionIds={','.join(option_ids)}"
greeks_resp = requests.get(greeks_url, headers=get_headers(), timeout=10).json()

print(f"\nGreeks API Response:")
print(f"  Status Code: (check response)")
print(f"  Response keys: {greeks_resp.keys()}")

option_greeks = greeks_resp.get("optionGreeks", [])
print(f"\nOption Greeks data ({len(option_greeks)} entries):")

for i, greek in enumerate(option_greeks, 1):
    print(f"\n  Option {i}:")
    print(f"    Symbol ID: {greek.get('symbolId')}")
    print(f"    Volatility: {greek.get('volatility')}")
    print(f"    Delta: {greek.get('delta')}")
    print(f"    Gamma: {greek.get('gamma')}")
    print(f"    Theta: {greek.get('theta')}")
    print(f"    Vega: {greek.get('vega')}")
    print(f"    Rho: {greek.get('rho')}")
    print(f"    All keys: {greek.keys()}")

if not option_greeks:
    print("\n  WARNING: No Greeks data returned!")
elif all(g.get('volatility', 0) == 0 for g in option_greeks):
    print("\n  WARNING: All volatility values are 0!")
    print("\n  Possible reasons:")
    print("    1. Market is closed (Greeks may not update outside market hours)")
    print("    2. Account type doesn't have access to Greeks data")
    print("    3. API endpoint issue")
