import requests, json, os
from datetime import datetime, timedelta

def get_trade_date():
    d = datetime.now()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')

def fetch_broker_top(date_str, top_n=30):
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date_str}&selectType=ALLBUT0999"
    try:
        resp = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.twse.com.tw/'}, timeout=30)
        data = resp.json()
        if data.get('stat') != 'OK' or not data.get('data'):
            return []
        results = []
        for row in data['data']:
            try:
                net = int(row[-1].replace(',','').replace('+',''))
                if net > 0:
                    results.append({'sym':row[0].strip(),'name':row[1].strip(),'net':net,'date':date_str,'buy':0,'sell':0})
            except: continue
        results.sort(key=lambda x: x['net'], reverse=True)
        return results[:top_n]
    except Exception as e:
        print(f"Error: {e}"); return []

def calc_consecutive(records):
    stock_history = {}
    for rec in sorted(records, key=lambda x: x['date']):
        stock_history.setdefault(rec['sym'], []).append(rec)
    result = {}
    for sym, history in stock_history.items():
        sorted_h = sorted(history, key=lambda x: x['date'], reverse=True)
        days = 1
        prev = datetime.strptime(sorted_h[0]['date'], '%Y%m%d')
        for i in range(1, len(sorted_h)):
            cur = datetime.strptime(sorted_h[i]['date'], '%Y%m%d')
            if (prev - cur).days <= 3:
                days += 1; prev = cur
            else: break
        nets = [r['net'] for r in sorted_h[:5]]
        result[sym] = {'name':sorted_h[0].get('name',sym),'consecutive_days':days,'is_increasing':len(nets)>=2 and nets[0]>=nets[1],'recent_nets':nets[:5],'total_net_5d':sum(nets),'last_date':sorted_h[0]['date']}
    return result

def main():
    date_str = get_trade_date()
    path = 'data/broker_data.json'
    existing = json.load(open(path,'r',encoding='utf-8')) if os.path.exists(path) else {'records':[],'consecutive':{},'today_top':[]}
    if not [r for r in existing.get('records',[]) if r['date']==date_str]:
        new = fetch_broker_top(date_str)
        existing['records'] = existing.get('records',[]) + new
        cutoff = (datetime.now()-timedelta(days=60)).strftime('%Y%m%d')
        existing['records'] = [r for r in existing['records'] if r['date']>=cutoff]
    existing['consecutive'] = calc_consecutive(existing['records'])
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing['fetch_date'] = date_str
    existing['today_top'] = sorted([r for r in existing['records'] if r['date']==date_str],key=lambda x:x['net'],reverse=True)[:20]
    os.makedirs('data',exist_ok=True)
    json.dump(existing, open('data/broker_data.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"✅ 完成，{len(existing['records'])} 筆記錄")

if __name__ == '__main__': main()
