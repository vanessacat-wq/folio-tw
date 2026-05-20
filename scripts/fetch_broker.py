import requests, json, os
from datetime import datetime, timedelta

def fetch_broker_top(date_str, top_n=30):
    results = []
    try:
        url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date_str}&selectType=ALLBUT0999"
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if data.get('stat') != 'OK' or not data.get('data'):
            print(f"[{date_str}] 證交所資料不可用")
            return []
        rows = data['data']
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
            except:
                continue
    except Exception as e:
        print(f"Error: {e}")
    return results

def calc_consecutive(records):
    from collections import defaultdict
    by_sym = defaultdict(list)
    for r in records:
        by_sym[r['sym']].append(r)
    result = {}
    for sym, recs in by_sym.items():
        recs = sorted(recs, key=lambda x: x['date'])
        days = 1
        nets = [recs[-1]['net']]
        for i in range(len(recs)-1, 0, -1):
            if recs[i]['net'] > 0 and recs[i-1]['net'] > 0:
                days += 1
                nets.append(recs[i-1]['net'])
            else:
                break
        nets = list(reversed(nets))
        is_inc = len(nets) >= 2 and nets[-1] >= nets[-2]
        result[sym] = {
            'sym': sym,
            'name': recs[-1].get('name', sym),
            'consecutive_days': days,
            'is_increasing': is_inc,
            'recent_nets': nets[-5:],
            'total_net_5d': sum(nets[-5:]),
            'last_date': recs[-1]['date']
        }
    return result

def main():
    today = datetime.now()
    if today.weekday() >= 5:
        today -= timedelta(days=today.weekday()-4)
    date_str = today.strftime('%Y%m%d')

    existing = {}
    try:
        with open('data/broker_data.json', 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except:
        existing = {'records': []}

    today_records = [r for r in existing.get('records', []) if r['date'] == date_str]
    if today_records:
        print(f"今日 {date_str} 資料已存在，跳過")
    else:
        print("抓取分點買超資料 ...")
        new_records = fetch_broker_top(date_str, top_n=30)
        print(f"取得 {len(new_records)} 筆記錄")
        if new_records:
            existing['records'] = existing.get('records', []) + new_records
            cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
            existing['records'] = [r for r in existing['records'] if r['date'] >= cutoff]

    consecutive = calc_consecutive(existing.get('records', []))
    existing['consecutive'] = consecutive
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing['fetch_date'] = date_str

    today_top = sorted(
        [r for r in existing.get('records', []) if r['date'] == date_str],
        key=lambda x: x['net'], reverse=True
    )[:20]
    existing['today_top'] = today_top

    os.makedirs('data', exist_ok=True)
    with open('data/broker_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"✅ broker_data.json 已更新，共 {len(existing.get('records', []))} 筆歷史記錄")

if __name__ == '__main__':
    main()
