import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os
import time

def get_trade_date():
    d = datetime.now()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')

def fetch_broker_top(date_str, top_n=30):
    results = []
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date_str}&selectType=ALLBUT0999"
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.twse.com.tw/'}
        resp = requests.get(url, headers=headers, timeout=30)
        data = resp.json()
        if data.get('stat') != 'OK' or not data.get('data'):
            print(f"[{date_str}] 資料不可用")
            return []
        for row in data['data']:
            try:
                sym = row[0].strip()
                name = row[1].strip()
                net = int(row[-1].replace(',', '').replace('+', ''))
                if net > 0:
                    results.append({'sym': sym, 'name': name, 'net': net, 'date': date_str, 'buy': 0, 'sell': 0})
            except:
                continue
        results.sort(key=lambda x: x['net'], reverse=True)
        return results[:top_n]
    except Exception as e:
        print(f"Error: {e}")
        return []

def calc_consecutive(records):
    stock_history = {}
    for rec in sorted(records, key=lambda x: x['date']):
        sym = rec['sym']
        if sym not in stock_history:
            stock_history[sym] = []
        stock_history[sym].append(rec)

    consecutive_data = {}
    for sym, history in stock_history.items():
        sorted_h = sorted(history, key=lambda x: x['date'], reverse=True)
        consecutive_days = 1
        prev_date = datetime.strptime(sorted_h[0]['date'], '%Y%m%d')
        for i in range(1, len(sorted_h)):
            cur_date = datetime.strptime(sorted_h[i]['date'], '%Y%m%d')
            diff = (prev_date - cur_date).days
            if diff <= 3:
                consecutive_days += 1
                prev_date = cur_date
            else:
                break
        nets = [r['net'] for r in sorted_h[:5]]
        is_increasing = len(nets) >= 2 and nets[0] >= nets[1]
        consecutive_data[sym] = {
            'name': sorted_h[0].get('name', sym),
            'consecutive_days': consecutive_days,
            'is_increasing': is_increasing,
            'recent_nets': nets[:5],
            'total_net_5d': sum(nets),
            'last_date': sorted_h[0]['date'],
        }
    return consecutive_data

def main():
    date_str = get_trade_date()
    print(f"抓取日期：{date_str}")
    path = 'data/broker_data.json'
    existing = json.load(open(path, 'r', encoding='utf-8')) if os.path.exists(path) else {'records': [], 'last_updated': '', 'consecutive': {}}

    today_records = [r for r in existing.get('records', []) if r['date'] == date_str]
    if not today_records:
        new_records = fetch_broker_top(date_str)
        print(f"取得 {len(new_records)} 筆")
        existing['records'] = existing.get('records', []) + new_records
        cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        existing['records'] = [r for r in existing['records'] if r['date'] >= cutoff]

    existing['consecutive'] = calc_consecutive(existing['records'])
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing['fetch_date'] = date_str
    today_top = sorted([r for r in existing['records'] if r['date'] == date_str], key=lambda x: x['net'], reverse=True)[:20]
    existing['today_top'] = today_top

    os.makedirs('data', exist_ok=True)
    with open('data/broker_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"✅ broker_data.json 更新完成，{len(existing['records'])} 筆記錄")

if __name__ == '__main__':
    main()
