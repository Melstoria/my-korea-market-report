import pandas as pd
import os
import glob
from datetime import datetime

INPUT_DIR = os.environ.get("INPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/input"))

SECTOR_MAP = {
    "반도체": ["SK하이닉스","삼성전자","한미반도체","DB하이텍","HPSP","리노공업","이오테크닉스","원익IPS","테크윙","피에스케이","주성엔지니어링","동진쎄미켐"],
    "2차전지": ["LG에너지솔루션","삼성SDI","에코프로","에코프로비엠","포스코퓨처엠","엘앤에프","천보","동화기업"],
    "바이오/제약": ["삼성바이오로직스","셀트리온","한미약품","유한양행","HLB","알테오젠","리가켐바이오"],
    "AI/소프트웨어": ["카카오","NAVER","더존비즈온","솔트룩스"],
    "자동차": ["현대차","기아","현대모비스","한온시스템","HL만도"],
    "금융": ["KB금융","신한지주","하나금융지주","우리금융지주","메리츠금융지주","삼성화재"],
    "건설/부동산": ["삼성물산","현대건설","GS건설","대우건설","HDC현대산업개발"],
    "방산/우주": ["한화에어로스페이스","LIG넥스원","한국항공우주","현대로템","한화시스템"],
    "조선/해운": ["HD한국조선해양","삼성중공업","한화오션","HMM","HD현대중공업"],
    "철강/화학": ["POSCO홀딩스","현대제철","LG화학","롯데케미칼","효성첨단소재"],
    "소비재/유통": ["LG생활건강","아모레퍼시픽","이마트","롯데쇼핑","신세계"],
    "통신": ["SK텔레콤","KT","LG유플러스"],
    "에너지": ["한국전력","SK이노베이션","한국가스공사"],
}

def classify_sector(name):
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in name:
                return sector
    return "기타"

def parse_date_from_filename(filename):
    base = os.path.basename(filename)
    date_part = base.split("_")[-1].replace(".xlsx","")
    try:
        d = datetime.strptime(date_part, "%y%m%d")
        return d.strftime("%Y-%m-%d")
    except:
        return datetime.today().strftime("%Y-%m-%d")

def parse_volume(filepath):
    df = pd.read_excel(filepath, header=None)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df.dropna(subset=["종목명"])
    results = []
    for i, row in df.iterrows():
        try:
            name = str(row.get("종목명","")).strip()
            if not name or name == "nan":
                continue
            ticker = str(row.get("종목코드","")).strip().zfill(6)
            close = float(str(row.get("현재가",0)).replace(",","") or 0)
            change_pct = float(str(row.get("등락률",0)).replace(",","").replace("%","") or 0)
            volume = int(float(str(row.get("거래량",0)).replace(",","") or 0))
            amount = float(str(row.get("거래대금",0)).replace(",","") or 0) / 100
            rank = int(float(str(row.get("순위",i+1))) or i+1)
            results.append({
                "rank": rank, "ticker": ticker, "name": name,
                "market": "KOSPI", "sector": classify_sector(name),
                "close": close, "change_pct": change_pct,
                "volume": volume, "amount": amount, "market_cap": 0,
            })
        except:
            continue
    results.sort(key=lambda x: x["amount"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    print(f"[Parser] 거래대금: {len(results)}개")
    return results

def parse_high(filepath):
    df = pd.read_excel(filepath, header=None)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df.dropna(subset=["종목명"])
    results = []
    for i, row in df.iterrows():
        try:
            name = str(row.get("종목명","")).strip()
            if not name or name == "nan":
                continue
            ticker = str(row.get("종목코드","")).strip().zfill(6)
            close = float(str(row.get("현재가",0)).replace(",","") or 0)
            change_pct = float(str(row.get("등락률",0)).replace(",","").replace("%","") or 0)
            high_52w = float(str(row.get("250일 고가",0)).replace(",","") or 0)
            if high_52w > 0 and close >= high_52w * 0.98:
                results.append({
                    "ticker": ticker, "name": name, "market": "KOSPI",
                    "sector": classify_sector(name), "close": close,
                    "change_pct": change_pct, "high_52w": high_52w,
                })
        except:
            continue
    print(f"[Parser] 신고가: {len(results)}개")
    return results

def find_latest_files(date_str=None):
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        suffix = d.strftime("%y%m%d")
        vol = os.path.join(INPUT_DIR, f"volume_{suffix}.xlsx")
        high = os.path.join(INPUT_DIR, f"high_{suffix}.xlsx")
        return (vol if os.path.exists(vol) else None,
                high if os.path.exists(high) else None)
    else:
        vol_files = sorted(glob.glob(os.path.join(INPUT_DIR, "volume_*.xlsx")), reverse=True)
        high_files = sorted(glob.glob(os.path.join(INPUT_DIR, "high_*.xlsx")), reverse=True)
        return (vol_files[0] if vol_files else None,
                high_files[0] if high_files else None)