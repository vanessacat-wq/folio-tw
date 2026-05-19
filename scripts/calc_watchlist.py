import json, os, requests
from datetime import datetime

def load_json(path):
    if os.path.exists(path):
        with open(path,'r',encoding='utf-8') as f: return json.load(f)
    return {}

def check_gates(sym, broker_data, chips_data):
    cons = broker_data.get('consecutive',{}).get(sym,{})
    chips = chips_data.get('stocks',{}).get(sym,{})
    days = cons.get('consecutive_days',0)
    is_inc = cons.get('is_increasing',False)
    gate1 = days >= 3 and is_inc
    gate1_detail = f"連續{days}天，{'遞增✅' if is_inc else '未遞增❌'}"
    gate2 = True
    gate2_detail = "成本判斷：待優化"
    trend = chips.get('trend','unknown')
    change_pct = chips.get('change_pct',0)
    gate3 = True if trend=='decreasing' else (False if trend=='increasing' else None)
    gate3_detail = f"戶數{'遞減✅' if trend=='decreasing' else '增加❌' if trend=='increasing' else '待確認'} {abs(change_pct):.1f}%"
    passed = sum(1 for g in [gate1,gate2,gate3] if g is True)
    return {'gate1':gate1,'gate2':gate2,'gate3':gate3,'gate1_detail':gate1_detail,'gate2_detail':gate2_detail,'gate3_detail':gate3_detail,'passed_count':passed,'all_pass':gate1 and gate2 and gate3 is not False}

def main():
    broker_data = load_json('data/broker_data.json')
    chips_data = load_json('data/chips_data.json')
    if not broker_data: print("無資料"); return
    all_syms = set(broker_data.get('consecutive',{}).keys())
    for item in broker_data.get('today_top',[]): all_syms.add(item['sym'])
    watchlist, observe_list = [], []
    for sym in all_syms:
        cons = broker_data.get('consecutive',{}).get(sym,{})
        chips = chips_data.get('stocks',{}).get(sym,{})
        gates = check_gates(sym, broker_data, chips_data)
        entry = {'sym':sym,'name':cons.get('name',sym),'consecutive_days':cons.get('consecutive_days',0),'is_increasing':cons.get('is_increasing',False),'recent_nets':cons.get('recent_nets',[]),'total_net_5d':cons.get('total_net_5d',0),'chips_trend':chips.get('trend','unknown'),'chips_change_pct':chips.get('change_pct',0),'gates':gates,'score':gates['passed_count'],'last_date':cons.get('last_date','')}
        if gates['all_pass']: watchlist.append(entry)
        elif gates['passed_count'] >= 1: observe_list.append(entry)
    watchlist.sort(key=lambda x:(-x['score'],-x['consecutive_days']))
    observe_list.sort(key=lambda x:(-x['score'],-x['consecutive_days']))
    output = {'last_updated':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'fetch_date':broker_data.get('fetch_date',''),'watchlist':watchlist[:10],'observe_list':observe_list[:20],'today_ranking':broker_data.get('today_top',[])[:20],'summary':{'all_pass':len(watchlist),'observing':len(observe_list)}}
    os.makedirs('data',exist_ok=True)
    json.dump(output, open('data/watchlist.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"✅ watchlist.json 完成，三關全過:{len(watchlist)}，觀察中:{len(observe_list)}")

if __name__ == '__main__': main()
