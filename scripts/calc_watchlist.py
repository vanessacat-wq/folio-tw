"""
calc_watchlist.py
整合分點買超 + 集保戶數，計算三關篩選結果
輸出 watchlist.json 給前端頁面使用
"""

import json
import os
import requests
from datetime import datetime

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def fetch_current_price(sym):
    """從 Yahoo Finance 抓現價"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.TW?interval=1d&range=1d"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        data = resp.json()
        meta = data['chart']['result'][0]['meta']
        return meta.get('regularMarketPrice', 0)
    except:
        return 0

def estimate_avg_cost(consecutive_info, broker_records, sym):
    """
    估算主力平均買進成本
    用近期連續買超期間的簡單平均（需要配合實際股價）
    """
    # 取得近5天的買超記錄
    recent_records = sorted(
        [r for r in broker_records if r['sym'] == sym],
        key=lambda x: x['date'], reverse=True
    )[:5]

    if not recent_records:
        return None

    # 這裡我們用買超張數加權（實際應乘以當日收盤價，但簡化版先用這個）
    total_net = sum(r['net'] for r in recent_records)
    return total_net  # 返回總淨買超張數作為參考

def check_three_gates(sym, broker_data, chips_data):
    """
    執行三關篩選：
    第一關：連續買超 3 天以上，且張數遞增
    第二關：現價不超過主力均價 5%（需要股價資料）
    第三關：集保戶數連續減少
    """
    consecutive = broker_data.get('consecutive', {}).get(sym, {})
    chips_info = chips_data.get('stocks', {}).get(sym, {})

    gates = {
        'gate1': False,
        'gate2': False,
        'gate3': False,
        'gate1_detail': '',
        'gate2_detail': '',
        'gate3_detail': '',
    }

    # ── 第一關：連續買超 ──
    days = consecutive.get('consecutive_days', 0)
    is_inc = consecutive.get('is_increasing', False)
    recent_nets = consecutive.get('recent_nets', [])

    if days >= 3:
        gates['gate1'] = True
        trend_str = '遞增✅' if is_inc else '未遞增⚠️'
        gates['gate1_detail'] = f"連續 {days} 天買超，張數{trend_str}，近期：{recent_nets[:3]}"
        if not is_inc:
            gates['gate1'] = False  # 要求遞增
            gates['gate1_detail'] += "（需張數遞增才過關）"
    else:
        gates['gate1_detail'] = f"連續 {days} 天，未達3天門檻"

    # ── 第二關：成本判斷 ──
    # 由於沒有精確的每日均價，改用現價 vs 近期高點判斷
    # 未來版本可加入每日收盤價對應
    gates['gate2'] = True  # 暫時預設通過，等有股價對應資料後再精算
    gates['gate2_detail'] = "成本估算需配合每日收盤價（下版本優化）"

    # ── 第三關：集保戶數 ──
    trend = chips_info.get('trend', 'unknown')
    change_pct = chips_info.get('change_pct', 0)
    latest_holders = chips_info.get('latest_holders', 0)

    if trend == 'decreasing':
        gates['gate3'] = True
        gates['gate3_detail'] = f"戶數遞減 {abs(change_pct):.1f}%，籌碼集中✅"
    elif trend == 'increasing':
        gates['gate3'] = False
        gates['gate3_detail'] = f"戶數增加 {change_pct:.1f}%，散戶湧入⚠️"
    elif trend == 'unknown' or not chips_info:
        gates['gate3'] = None  # 資料不足，標記為待確認
        gates['gate3_detail'] = "集保資料待取得"
    else:
        gates['gate3'] = False
        gates['gate3_detail'] = "戶數穩定，無明顯集中"

    # 計算通過幾關
    passed = sum(1 for g in [gates['gate1'], gates['gate2'], gates['gate3']] if g is True)
    gates['passed_count'] = passed
    gates['all_pass'] = gates['gate1'] and gates['gate2'] and (gates['gate3'] is not False)

    return gates

def main():
    print("計算三關篩選結果...")

    broker_data = load_json('data/broker_data.json')
    chips_data = load_json('data/chips_data.json')

    if not broker_data:
        print("broker_data.json 不存在，跳過")
        return

    consecutive = broker_data.get('consecutive', {})
    today_top = broker_data.get('today_top', [])

    # 所有需要評估的股票（連續買超 + 今日前20）
    all_syms = set(consecutive.keys())
    for item in today_top:
        all_syms.add(item['sym'])

    watchlist = []
    observe_list = []

    for sym in all_syms:
        cons_info = consecutive.get(sym, {})
        name = cons_info.get('name', sym)

        gates = check_three_gates(sym, broker_data, chips_data)

        entry = {
            'sym': sym,
            'name': name,
            'consecutive_days': cons_info.get('consecutive_days', 0),
            'is_increasing': cons_info.get('is_increasing', False),
            'recent_nets': cons_info.get('recent_nets', []),
            'total_net_5d': cons_info.get('total_net_5d', 0),
            'chips_trend': chips_data.get('stocks', {}).get(sym, {}).get('trend', 'unknown'),
            'chips_change_pct': chips_data.get('stocks', {}).get(sym, {}).get('change_pct', 0),
            'gates': gates,
            'score': gates['passed_count'],
            'last_date': cons_info.get('last_date', ''),
        }

        if gates['all_pass']:
            watchlist.append(entry)
        elif gates['passed_count'] >= 1:
            observe_list.append(entry)

    # 排序：通過關數多的在前，再按連續天數
    watchlist.sort(key=lambda x: (-x['score'], -x['consecutive_days']))
    observe_list.sort(key=lambda x: (-x['score'], -x['consecutive_days']))

    # 今日買超排行（原始資料）
    today_ranking = sorted(today_top, key=lambda x: x['net'], reverse=True)[:20]

    output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'fetch_date': broker_data.get('fetch_date', ''),
        'watchlist': watchlist[:10],       # 三關全過，最多10檔
        'observe_list': observe_list[:20], # 一到兩關，觀察中
        'today_ranking': today_ranking,    # 今日買超排行
        'total_tracked': len(all_syms),
        'summary': {
            'all_pass': len(watchlist),
            'observing': len(observe_list),
            'today_top_count': len(today_ranking),
        }
    }

    os.makedirs('data', exist_ok=True)
    with open('data/watchlist.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ watchlist.json 已更新")
    print(f"   三關全過：{len(watchlist)} 檔")
    print(f"   觀察中：{len(observe_list)} 檔")
    print(f"   今日買超排行：{len(today_ranking)} 檔")

if __name__ == '__main__':
    main()
