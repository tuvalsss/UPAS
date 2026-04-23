import time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from core.engine import run_pipeline
from tools.account_tool import get_polymarket_account
from tools.database_tool import get_recent_orders

for i in range(3):
    print(f'\n====== CYCLE {i+1}/3 ======')
    pa = get_polymarket_account()
    print(f'cash=${pa.get("cash_balance_usd",0)} pos=${pa.get("positions_value_usd",0)} open={pa.get("open_orders",0)}')
    r = run_pipeline(non_interactive=True)
    print(f'orders_placed={r.get("orders_placed",0)}')
    live = [o for o in get_recent_orders(hours=1) if not o.get("dry_run")]
    if live:
        o = live[0]
        print(f'  last: {o.get("status")} {o.get("side")} @${o.get("price")} size=${o.get("size_usd")} err={o.get("error","")[:80] if o.get("error") else "ok"}')
    if i < 2:
        time.sleep(90)

print('\n=== DONE ===')
pa = get_polymarket_account()
print(f'final: cash=${pa.get("cash_balance_usd",0)} pos=${pa.get("positions_value_usd",0)} open={pa.get("open_orders",0)}')
