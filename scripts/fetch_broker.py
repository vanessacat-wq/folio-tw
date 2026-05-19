"""
fetch_broker.py
每日收盤後抓取台灣證交所券商分點買超資料
資料來源：台灣證交所 opendata
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os
import time

def get_trade_date():
    """取得最近交易日（週一到週五）"""
    d = datetime.now()
    # 如果是週六(5)或週日(6)，往回找
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')

def fetch_broker_top(date_str, top_n=20):
    """
    抓取指定日期的分點買超排行
    來源：證交所每日分點進出明細
    """
    results = []

    # 證交所分點買超資料 API
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT43U?response=json&date={date_str}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; DataFetcher/1.0)',
            'Referer': 'https://www.twse.com.tw/'
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get('stat') != 'OK' or not data.get('data'):
            print(f"[{date_str}] 證交所資料不可用，可能為假日或資料尚未更新")
            return []

        rows = data['data']
        # 欄位：[股票代號, 股票名稱, 買進張數, 賣出張數, 買賣差]
        for row in rows[:top_n]:
            try:
                sym = row[0].strip()
                name = row[1].strip()
                buy = int(row[2].replace(',', ''))
                sell = int(row[3].replace(',', ''))
                net = int(row[4].replace(',', ''))
                if net > 0:
                    results.append({
                        'sym': sym,
                        'name': name,
                        'buy': buy,
                        'sell': sell,
                        'net': net,
                        'date': date_str
                    })
            except Exception as e:
                continue

    except Exception as e:
        print(f"Error fetching broker data: {e}")

    # 備用：使用三大法人+融資融券概念作為替代分點信號
    # 從 TWSE 個股買賣日報
    if not results:
        results = fetch_alternative_signals(date_str, top_n)

    return results

def fetch_alternative_signals(date_str, top_n=20):
    """
    備用方案：抓取外資+投信合計買超前N名
    當分點資料無法取得時使用
    """
    results = []
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date_str}&selectType=ALLBUT0999"

    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.twse.com.tw/'}
        resp = requests.get(url, headers=headers, timeout=30)
        data = resp.json()

        if data.get('stat') != 'OK' or not data.get('data'):
            return []

        rows = data['data']
        parsed = []
        for row in rows:
            try:
                sym = row[0].strip()
                name = row[1].strip()
                # 三大法人合計 (最後一欄)
                total_net = int(row[-1].replace(',', '').replace('+', ''))
                parsed.append({'sym': sym, 'name': name, 'net': total_net, 'date': date_str,
                               'buy': 0, 'sell': 0, 'source': 'institutional'})
            except:
                continue

        # 依淨買超排序，取前N名
        parsed.sort(key=lambda x: x['net'], reverse=True)
        results = [r for r in parsed if r['net'] > 0][:top_n]

    except Exception as e:
        print(f"Alternative signal fetch error: {e}")

    return results

def load_existing_data():
    """載入現有歷史資料"""
    path = 'data/broker_data.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'records': [], 'last_updated': '', 'consecutive': {}}

def calc_consecutive(records):
    """
    計算每檔股票的連續買超天數、張數趨勢、平均成本
    records: 按日期排列的買超記錄
    """
    # 按股票分組
    stock_history = {}
    for rec in sorted(records, key=lambda x: x['date']):
        sym = rec['sym']
        if sym not in stock_history:
            stock_history[sym] = []
        stock_history[sym].append(rec)

    consecutive_data = {}
    for sym, history in stock_history.items():
        if len(history) < 1:
            continue

        # 計算連續天數（最近的連續記錄）
        sorted_h = sorted(history, key=lambda x: x['date'], reverse=True)
        consecutive_days = 1
        prev_date = datetime.strptime(sorted_h[0]['date'], '%Y%m%d')

        for i in range(1, len(sorted_h)):
            cur_date = datetime.strptime(sorted_h[i]['date'], '%Y%m%d')
            diff = (prev_date - cur_date).days
            # 允許週末間隔
            if diff <= 3:
                consecutive_days += 1
                prev_date = cur_date
            else:
                break

        # 取最近5天計算平均淨買超（判斷是否遞增）
        recent = sorted_h[:5]
        nets = [r['net'] for r in recent]
        is_increasing = len(nets) >= 2 and nets[0] >= nets[1]  # 最新 >= 前一天

        # 平均買進成本（用張數加權，這裡用淨買超張數近似）
        total_net = sum(r['net'] for r in sorted_h[:5])

        consecutive_data[sym] = {
            'name': sorted_h[0].get('name', sym),
            'consecutive_days': consecutive_days,
            'is_increasing': is_increasing,
            'recent_nets': nets[:5],
            'total_net_5d': total_net,
            'last_date': sorted_h[0]['date'],
        }

    return consecutive_data

def main():
    date_str = get_trade_date()
    print(f"抓取日期：{date_str}")

    # 載入現有資料
    existing = load_existing_data()

    # 檢查今天是否已抓過
    today_records = [r for r in existing.get('records', []) if r['date'] == date_str]
    if today_records:
        print(f"今日 {date_str} 資料已存在，跳過")
    else:
        # 抓取今日資料
        print("抓取分點買超資料...")
        new_records = fetch_broker_top(date_str, top_n=30)
        print(f"取得 {len(new_records)} 筆記錄")

        if new_records:
            existing['records'] = existing.get('records', []) + new_records
            # 只保留最近60天資料
            cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
            existing['records'] = [r for r in existing['records'] if r['date'] >= cutoff]

    # 重新計算連續統計
    existing['consecutive'] = calc_consecutive(existing['records'])
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing['fetch_date'] = date_str

    # 取得今日買超排行（前20）
    today_top = sorted(
        [r for r in existing['records'] if r['date'] == date_str],
        key=lambda x: x['net'], reverse=True
    )[:20]
    existing['today_top'] = today_top

    # 儲存
    os.makedirs('data', exist_ok=True)
    with open('data/broker_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✅ broker_data.json 已更新，共 {len(existing['records'])} 筆歷史記錄")

if __name__ == '__main__':
    main()
