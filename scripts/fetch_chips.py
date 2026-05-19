import requests, json, os, time
from datetime import datetime, timedelta

def fetch_tdcc_holders(stock_code):
    try:
        url = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
        headers = {'User-Agent':'Mozilla/5.0','Content-Type':'application/x-www-form-urlencoded','Referer':'https://www.tdcc.com.tw/portal/zh/smWeb/qryStock'}
        resp = requests.post(url, data={'sqlMethod':'historyQuery','stockNo':stock_code,'REQ_TYPE':''}, headers=headers, timeout=30)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return [{'date':item.get('scaDate',''),'holders':int(str(item.get('stdyHolderCnt',0)).replace(',',''))} for item in data[-4:]]
    except: pass
    return []

def analyze_trend(history):
    holders = [h['holders'] for h in history if h['holders'] > 0]
    if len(holders) < 2: return 'unknown', 0
    change = holders[-1] - holders[0]
    change_pct = (change / holders[0] * 100) if holders[0] > 0 else 0
    return ('decreasing' if change < 0 else 'increasing' if change > 0 else 'stable'), round(change_pct, 2)

def main():
    broker_path = 'data/broker_data.json'
    if not os.path.exists(broker_path):
        print("broker_data.json 不存在"); return
    broker_data = json.load(open(broker_path,'r',encoding='utf-8'))
    consecutive = broker_data.get('consecutive',{})
    targets = [sym for sym,info in consecutive.items() if info.get('consecutive_days',0)>=3]
    for item in broker_data.get('today_top',[])[:10]:
        if item['sym'] not in targets: targets.append(item['sym'])
    chips_path = 'data/chips_data.json'
    existing = json.load(open(chips_path,'r',encoding='utf-8')) if os.path.exists(chips_path) else {'stocks':{}}
    for sym in targets[:15]:
        print(f"  抓取 {sym}...")
        history = fetch_tdcc_holders(sym)
        trend, change_pct = analyze_trend(history)
        existing['stocks'][sym] = {'sym':sym,'history':history,'trend':trend,'change_pct':change_pct,'latest_holders':history[-1]['holders'] if history else 0,'last_updated':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        time.sleep(1)
    existing['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs('data',exist_ok=True)
    json.dump(existing, open('data/chips_data.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"✅ chips_data.json 完成，{len(existing['stocks'])} 檔")

if __name__ == '__main__': main()
