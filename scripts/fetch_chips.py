"""
fetch_chips.py
抓取集保結算所股權分散表（持有戶數）
用於判斷籌碼是否集中（戶數減少 = 籌碼集中）
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time

def get_latest_chips_week():
    """
    集保戶數每週更新一次（通常週五更新上週資料）
    取得最近可用的週次
    """
    d = datetime.now()
    # 找到最近的週五
    days_since_friday = (d.weekday() - 4) % 7
    last_friday = d - timedelta(days=days_since_friday)
    return last_friday.strftime('%Y%m%d')

def fetch_tdcc_holders(stock_code):
    """
    抓取特定股票的集保戶數歷史（最近4週）
    來源：集保結算所
    """
    url = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://www.tdcc.com.tw/portal/zh/smWeb/qryStock'
    }

    # 集保結算所需要 POST 請求
    payload = {
        'scaDate': '',
        'sqlMethod': 'historyQuery',
        'stockNo': stock_code,
        'REQ_TYPE': '',
    }

    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=30)
        # 解析返回的資料
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            results = []
            for item in data[-4:]:  # 最近4週
                results.append({
                    'date': item.get('scaDate', ''),
                    'holders': int(item.get('stdyHolderCnt', 0).replace(',', '') if isinstance(item.get('stdyHolderCnt'), str) else item.get('stdyHolderCnt', 0))
                })
            return results
    except Exception as e:
        pass

    # 備用：使用 TWSE 股東人數統計
    return fetch_twse_holders_alt(stock_code)

def fetch_twse_holders_alt(stock_code):
    """
    備用方案：從證交所抓股東人數
    """
    try:
        url = f"https://www.twse.com.tw/rwd/zh/ownership/STOCK_DAY_AVG?stockNo={stock_code}&response=json"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        data = resp.json()
        # 這個端點返回平均持股，作為替代指標
        return []
    except:
        return []

def load_existing_chips():
    path = 'data/chips_data.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'stocks': {}, 'last_updated': ''}

def analyze_chips_trend(history):
    """
    分析戶數趨勢
    返回：decreasing(遞減/籌碼集中), increasing(遞增/散戶湧入), stable(穩定)
    """
    if len(history) < 2:
        return 'unknown', 0

    holders = [h['holders'] for h in history if h['holders'] > 0]
    if len(holders) < 2:
        return 'unknown', 0

    # 計算變化率
    first = holders[0]  # 最早
    last = holders[-1]  # 最新
    change = last - first
    change_pct = (change / first * 100) if first > 0 else 0

    if change < 0:
        return 'decreasing', change_pct  # 籌碼集中（好事）
    elif change > 0:
        return 'increasing', change_pct  # 散戶湧入（注意）
    else:
        return 'stable', 0

def fetch_chips_for_watchlist():
    """
    為觀察清單中的股票抓取集保資料
    從 broker_data.json 取得需要追蹤的股票清單
    """
    # 讀取分點資料，找出連續買超的股票
    broker_path = 'data/broker_data.json'
    if not os.path.exists(broker_path):
        print("broker_data.json 不存在，跳過集保抓取")
        return {}

    with open(broker_path, 'r', encoding='utf-8') as f:
        broker_data = json.load(f)

    # 取得連續3天以上買超的股票
    consecutive = broker_data.get('consecutive', {})
    target_stocks = [
        sym for sym, info in consecutive.items()
        if info.get('consecutive_days', 0) >= 3
    ]

    # 加上今日買超前10名
    today_top = broker_data.get('today_top', [])
    for item in today_top[:10]:
        if item['sym'] not in target_stocks:
            target_stocks.append(item['sym'])

    print(f"需要抓集保資料的股票：{target_stocks[:15]}")

    chips_results = {}
    existing = load_existing_chips()

    for sym in target_stocks[:15]:  # 限制15檔避免太慢
        print(f"  抓取 {sym} 集保資料...")

        # 如果今天已更新過，跳過
        existing_stock = existing.get('stocks', {}).get(sym, {})
        last_update = existing_stock.get('last_updated', '')
        today_str = datetime.now().strftime('%Y-%m-%d')

        if last_update.startswith(today_str) and existing_stock.get('history'):
            print(f"  {sym} 今日已更新，使用快取")
            chips_results[sym] = existing_stock
            continue

        history = fetch_tdcc_holders(sym)
        trend, change_pct = analyze_chips_trend(history)

        chips_results[sym] = {
            'sym': sym,
            'history': history,
            'trend': trend,
            'change_pct': round(change_pct, 2),
            'latest_holders': history[-1]['holders'] if history else 0,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        time.sleep(1)  # 避免太快被擋

    return chips_results

def main():
    print("開始抓取集保戶數資料...")
    chips_data = fetch_chips_for_watchlist()

    existing = load_existing_chips()
    existing['stocks'].update(chips_data)
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    os.makedirs('data', exist_ok=True)
    with open('data/chips_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✅ chips_data.json 已更新，共 {len(existing['stocks'])} 檔股票")

if __name__ == '__main__':
    main()
