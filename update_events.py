#!/usr/bin/env python3
"""
자동 events.json 업데이트 스크립트
- FRED API로 미국 실제 발표값 조회 → result/done 자동 갱신
- 컨센서스는 hardcoded 테이블 (주기적으로 Claude가 업데이트)
"""

import json
import os
import requests
from datetime import datetime, timezone, timedelta

FRED_KEY = os.environ.get('FRED_API_KEY', '')
FRED_BASE = 'https://api.stlouisfed.org/fred/series/observations'

# KST 기준 오늘
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).date()

# ── FRED 시리즈 ID 매핑 ──────────────────────────────────────────
# event id → (fred_series_id, result_format_func)
def fmt_nfp(val):
    """비농업 고용 (천명 단위로 옴 → 만명 변환)"""
    try:
        v = float(val)
        return f"비농업 +{v/10:.0f}만명"
    except:
        return val

def fmt_unrate(val):
    try:
        return f"실업률 {float(val):.1f}%"
    except:
        return val

def fmt_cpi(val):
    try:
        return f"CPI 전년비 +{float(val):.1f}%"
    except:
        return val

def fmt_ppi(val):
    try:
        return f"PPI 전월비 {float(val):+.1f}%"
    except:
        return val

def fmt_pce(val):
    try:
        return f"PCE 전년비 +{float(val):.1f}%"
    except:
        return val

def fmt_gdp(val):
    try:
        return f"GDP 성장률 연율 +{float(val):.1f}%"
    except:
        return val

def fmt_ism(val):
    try:
        return f"ISM 제조업 PMI {float(val):.1f}"
    except:
        return val

# event_id → FRED series (관측값 날짜 기준으로 매칭)
FRED_MAP = {
    'e3':  [('PAYEMS', fmt_nfp), ('UNRATE', fmt_unrate)],   # 고용 8월
    'e4':  [('MANEMP', fmt_ism)],                            # ISM PMI (근사값)
    'e5':  [('CPIAUCSL', fmt_cpi)],                          # CPI 8월
    'e6':  [('PPIACO', fmt_ppi)],                            # PPI 8월
    'e8':  [('PCEPI', fmt_pce)],                             # PCE 8월
    'e9':  [('A191RL1Q225SBEA', fmt_gdp)],                   # GDP Q2
    'e10': [('PAYEMS', fmt_nfp), ('UNRATE', fmt_unrate)],   # 고용 9월
    'e11': [('CPIAUCSL', fmt_cpi)],                          # CPI 9월
    'e13': [('PCEPI', fmt_pce)],                             # PCE 9월
    'e14': [('PAYEMS', fmt_nfp), ('UNRATE', fmt_unrate)],   # 고용 10월
    'e18': [('CPIAUCSL', fmt_cpi)],                          # CPI 11월
}

def fred_latest(series_id, after_date_str):
    """after_date 이후 최신 관측값 반환. 없으면 None."""
    if not FRED_KEY:
        return None
    try:
        r = requests.get(FRED_BASE, params={
            'series_id': series_id,
            'api_key': FRED_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 3,
            'observation_start': after_date_str,
        }, timeout=10)
        data = r.json()
        obs = [o for o in data.get('observations', []) if o['value'] != '.']
        if obs:
            return obs[0]['value']
    except Exception as e:
        print(f"FRED error {series_id}: {e}")
    return None

def main():
    with open('events.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = False
    today_str = TODAY.isoformat()

    for ev in data['events']:
        if ev.get('done'):
            continue

        ev_date = ev['date']
        # 이벤트 날짜가 오늘 이전이어야 결과가 있을 수 있음
        if ev_date > today_str:
            continue

        ev_id = ev['id']
        if ev_id not in FRED_MAP:
            # FRED 매핑 없는 이벤트 (금통위, FOMC) → 날짜 지났으면 done만 표시
            ev['done'] = True
            ev['result'] = ev.get('result') or '발표 완료 (수동 입력 필요)'
            changed = True
            print(f"  done (no FRED): {ev['name']}")
            continue

        # FRED로 실제값 조회
        parts = []
        for series_id, fmt_fn in FRED_MAP[ev_id]:
            val = fred_latest(series_id, ev_date)
            if val:
                parts.append(fmt_fn(val))

        if parts:
            result_str = ' · '.join(parts)
            if ev.get('result') != result_str:
                ev['result'] = result_str
                ev['done'] = True
                print(f"  updated: {ev['name']} → {result_str}")
                changed = True
        else:
            print(f"  no data yet: {ev['name']}")

    if changed:
        # version 날짜 갱신
        data['version'] = today_str
        with open('events.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"events.json saved (version: {today_str})")
    else:
        print("no changes")

if __name__ == '__main__':
    main()
