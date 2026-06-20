"""
Korea Market Parser v2
영웅문 엑셀/CSV 파일 파싱

파일명 규칙 (data/input/ 폴더):
  volume_kospi_YYMMDD.xlsx/.csv   → KOSPI 거래대금 상위
  volume_kosdaq_YYMMDD.xlsx/.csv  → KOSDAQ 거래대금 상위
  high_YYMMDD.xlsx/.csv           → 신고가 (통합)

* 구버전 호환: volume_YYMMDD.xlsx/.csv → 통합 처리
"""

import pandas as pd
import os
import glob
import re
from datetime import datetime

INPUT_DIR = os.environ.get(
    "INPUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/input")
)

# ── 섹터 매핑 ─────────────────────────────────────────────────────────────────

SECTOR_MAP = {
    "반도체/하드웨어": [
        "SK하이닉스","삼성전자","한미반도체","DB하이텍","HPSP","리노공업",
        "이오테크닉스","원익IPS","테크윙","피에스케이","주성엔지니어링",
        "동진쎄미켐","솔브레인","덕산네오룩스","ISC","와이씨","에스앤에스텍",
        "SFA반도체","하나마이크론","네패스","이수페타시스","심텍","제주반도체",
        "가온칩스","오로스테크놀로지","코미코","한솔케미칼","삼화콘덴서",
        "파두","테스","브이엠","에이치브이엠","성호전자","필옵틱스","예스티",
        "서진시스템","에스에이엠티","유진테크","대주전자재료","스피어",
        "티에스이","티씨케이","서울반도체","미코","RFHIC","인텍플러스",
        "한울반도체","지오엘리먼트",
    ],
    "반도체 장비/소부장": [
        "원익IPS","피에스케이","주성엔지니어링","테크윙","이오테크닉스",
        "에스티아이","레이저쎌","HB테크놀러지","브이원텍","디엔에프",
        "솔브레인홀딩스","한양이엔지","GST","오션브릿지","HPSP",
        "고영","우리기술","현대힘스","태성",
    ],
    "전기전자/부품": [
        "삼성전기","LG이노텍","LG전자","삼성SDI",
        "LS ELECTRIC","효성중공업","효성첨단소재","LS","LS일렉트릭",
        "대한전선","일진전기","LS에코에너지","HD현대일렉트릭","현대일렉트릭",
        "삼성디스플레이","LG디스플레이","SK스퀘어","SKC",
        "제룡전기","아이티센글로벌",
    ],
    "빅테크/플랫폼": [
        "카카오","NAVER","더존비즈온","솔트룩스","카카오뱅크","카카오페이",
        "크래프톤","넷마블","엔씨소프트","NHN","카카오게임즈",
        "시프트업","NC","넥슨","컴투스","게임빌","펄어비스","실리콘투",
    ],
    "자동차/부품": [
        "현대차","기아","현대모비스","한온시스템","HL만도","현대위아",
        "성우하이텍","서연이화","화신","세종공업","평화정공","현대글로비스",
    ],
    "2차전지/소재": [
        "LG에너지솔루션","에코프로","에코프로비엠","포스코퓨처엠",
        "엘앤에프","천보","동화기업","솔루스첨단소재","에코프로HN",
        "코스모신소재","나노신소재","후성","일진머티리얼즈","엔켐","비나텍",
    ],
    "바이오/헬스케어": [
        "삼성바이오로직스","셀트리온","한미약품","유한양행","HLB","알테오젠",
        "리가켐바이오","오스코텍","에이비엘바이오","보로노이","한올바이오파마",
        "동아에스티","종근당","대웅제약","휴온스","일동제약","보령",
        "디앤디파마텍","오스템임플란트","클래시스","파마리서치","메디톡스",
        "펩트론","알지노믹스","엘앤씨바이오","삼천당제약","올릭스","코오롱티슈진",
        "제이앤티씨","오름테라퓨틱","네이처셀","에이프릴바이오","이퓨쳐",
    ],
    "로보틱스/자동화": [
        "레인보우로보틱스","두산로보틱스","현대로보틱스","에스피지","스맥",
        "티로보틱스","유진로봇","로보스타","한화로보틱스",
        "로보티즈","현대무벡스","코스모로보틱스","와이지-원","비에이치아이",
    ],
    "방산/우주": [
        "한화에어로스페이스","LIG넥스원","한국항공우주","현대로템","한화시스템",
        "빅텍","퍼스텍","아스트","한국화이버","이노스페이스","LIG","한화",
    ],
    "조선/중공업": [
        "HD한국조선해양","삼성중공업","한화오션","HD현대중공업","HMM",
        "현대미포조선","대한해운","팬오션","HD현대","두산에너빌리티",
    ],
    "건설/플랜트": [
        "삼성물산","현대건설","GS건설","대우건설","HDC현대산업개발",
        "DL이앤씨","포스코이앤씨","SK에코플랜트","태영건설",
        "남화토건","강동씨앤엘",
    ],
    "금융": [
        "KB금융","신한지주","하나금융지주","우리금융지주","메리츠금융지주",
        "삼성화재","현대해상","DB손해보험","삼성생명","한화생명",
        "키움증권","미래에셋증권","삼성증권","NH투자증권","한국금융지주",
        "미래에셋생명","교보생명","흥국화재","현대차증권","미래에셋벤처투자",
    ],
    "에너지/유틸리티": [
        "한국전력","SK이노베이션","한국가스공사","S-Oil","GS","E1",
        "한전KPS","한전기술","SK에너지","에쓰오일",
    ],
    "지주/복합기업": [
        "SK","SK이노베이션","SK스퀘어","LG","롯데지주","한화","두산",
        "GS홀딩스","LS","CJ","CJ제일제당","한진칼","현대엘리베이터",
    ],
    "통신/광통신": [
        "SK텔레콤","KT","LG유플러스","KT스카이라이프",
        "오이솔루션","파인텍","우리로","화신테크","대한광통신",
    ],
    "철강/소재": [
        "POSCO홀딩스","현대제철","LG화학","롯데케미칼",
        "고려아연","풍산","영풍","세아베스틸지주","OCI","금호석유",
    ],
    "소비재/유통": [
        "LG생활건강","아모레퍼시픽","이마트","롯데쇼핑","신세계",
        "호텔신라","GKL","파라다이스","오리온","하이브","SM","YG","JYP",
        "한울앤제주",
    ],
}

ETF_KEYWORDS = [" ETN", "ETN(", "ETN "]  # 신고가 파싱 시 ETN만 제외

def classify_sector(name: str) -> str:
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in name:
                return sector
    return "기타"


# ── 날짜 파싱 ─────────────────────────────────────────────────────────────────

def parse_date_from_filename(filename: str) -> str:
    base = os.path.basename(filename)
    m = re.search(r'(\d{6})\.(xlsx|csv)$', base, re.I)
    if m:
        try:
            return datetime.strptime(m.group(1), "%y%m%d").strftime("%Y-%m-%d")
        except:
            pass
    return datetime.today().strftime("%Y-%m-%d")


# ── 공통 파일 읽기 ────────────────────────────────────────────────────────────

def _read_file(filepath: str) -> pd.DataFrame:
    """xlsx 또는 csv 자동 감지해서 읽기"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.csv':
        for enc in ['cp949', 'utf-8', 'euc-kr']:
            try:
                df = pd.read_csv(filepath, encoding=enc, header=0)
                return df
            except UnicodeDecodeError:
                continue
        raise ValueError(f"CSV 인코딩 감지 실패: {filepath}")
    else:
        df = pd.read_excel(filepath, header=None)
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        return df


# ── 거래대금 파싱 ─────────────────────────────────────────────────────────────

def parse_volume(filepath: str, market: str = None) -> list[dict]:
    if market is None:
        base = os.path.basename(filepath).lower()
        if 'kospi' in base:
            market = 'KOSPI'
        elif 'kosdaq' in base:
            market = 'KOSDAQ'
        else:
            market = 'MIXED'

    df = _read_file(filepath)
    df = df.dropna(subset=["종목명"])

    results = []
    for i, row in df.iterrows():
        try:
            name = str(row.get("종목명", "")).strip()
            if not name or name == "nan":
                continue
            # 영웅문 CSV: 종목코드 앞에 ' 붙는 경우 제거
            ticker = str(row.get("종목코드", "")).strip().lstrip("'").zfill(6)
            close  = _to_float(row.get("현재가", 0))
            chg    = _to_float(row.get("등락률", 0))
            vol    = _to_int(row.get("거래량", 0))
            amt    = _to_float(row.get("거래대금", 0))
            rank = _to_int(row.get("순위", i + 1)) or (i + 1)
            prev_rank = _to_int(row.get("전일", 0))

            results.append({
                "rank": rank, "ticker": ticker, "name": name,
                "market": market, "sector": classify_sector(name),
                "close": close, "change_pct": chg,
                "volume": vol, "amount": 0,  # 아래서 재계산
                "_raw_amount": amt,
                "market_cap": 0,
                "prev_rank": prev_rank,
            })
        except:
            continue

    # 거래대금 단위 자동 보정 (삼성전자 기준: ~27,000억 = 2.7조)
    # raw_amount 중간값으로 단위 추정
    raw_amounts = [r["_raw_amount"] for r in results if r["_raw_amount"] > 0]
    if raw_amounts:
        # 영웅문 [0184] 거래대금 단위: 백만원 (KOSPI/KOSDAQ 동일)
        # 검증: 거래량×주가 역산으로 확인 (비율 0.97~1.07, 오차 5% 이내)
        # 백만원 → 억원: ÷ 100
        # 예) SK하이닉스 34,707,849 ÷ 100 = 347,078억 = 34.7조 ✅
        # 예) 한화에어로  592,930 ÷ 100 = 5,929억 ✅ (네이버 5,127억, 장중/마감 차이)
        # 예) 제주반도체  972,942 ÷ 100 = 9,729억 ✅ (네이버 9,697억)
        top1 = max(raw_amounts)
        if top1 >= 100:
            divisor = 100      # 백만원 → 억원
        else:
            divisor = 1        # 이미 억원
        for r in results:
            r["amount"] = round(r["_raw_amount"] / divisor, 2)
            del r["_raw_amount"]
    else:
        for r in results:
            r.pop("_raw_amount", None)

    results.sort(key=lambda x: x["amount"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i

    print(f"[Parser] 거래대금({market}): {len(results)}개  (TOP 거래대금: {results[0]['amount']:.0f}억 / {results[0]['name']})")
    return results


# ── 신고가 파싱 ───────────────────────────────────────────────────────────────

def parse_high(filepath: str) -> list[dict]:
    df = _read_file(filepath)
    df = df.dropna(subset=["종목명"])

    results = []
    for i, row in df.iterrows():
        try:
            name = str(row.get("종목명", "")).strip()
            if not name or name == "nan":
                continue
            ticker = str(row.get("종목코드", "")).strip().lstrip("'").zfill(6)
            close  = _to_float(row.get("현재가", 0))
            chg    = _to_float(row.get("등락률", 0))
            high52 = _to_float(row.get("250일 고가", 0))
            vol_ratio = _to_float(row.get("전일거래량대비", 1)) or 1

            # ETF 제외
            if any(k in name for k in ETF_KEYWORDS):
                continue

            results.append({
                "ticker": ticker, "name": name,
                "market": _guess_market(ticker),
                "sector": classify_sector(name),
                "close": close, "change_pct": chg,
                "high_52w": high52, "vol_ratio": vol_ratio,
            })
        except:
            continue

    print(f"[Parser] 신고가: {len(results)}개")
    return results


# ── 파일 탐색 ─────────────────────────────────────────────────────────────────

def find_latest_files(date_str: str = None) -> dict:
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        suffix = d.strftime("%y%m%d")
        return {
            "date":       date_str,
            "kospi_vol":  _find_any(f"volume_kospi_{suffix}"),
            "kosdaq_vol": _find_any(f"volume_kosdaq_{suffix}"),
            "volume":     _find_any(f"volume_{suffix}"),
            "high":       _find_any(f"high_{suffix}"),
            "high_kospi":  _find_any(f"high_kospi_{suffix}"),
            "high_kosdaq": _find_any(f"high_kosdaq_{suffix}"),
        }
    else:
        all_files = (
            glob.glob(os.path.join(INPUT_DIR, "volume_kospi_*.xlsx")) +
            glob.glob(os.path.join(INPUT_DIR, "volume_kospi_*.csv")) +
            glob.glob(os.path.join(INPUT_DIR, "volume_kosdaq_*.xlsx")) +
            glob.glob(os.path.join(INPUT_DIR, "volume_kosdaq_*.csv")) +
            glob.glob(os.path.join(INPUT_DIR, "volume_*.xlsx")) +
            glob.glob(os.path.join(INPUT_DIR, "volume_*.csv"))
        )
        if not all_files:
            return {"date": datetime.today().strftime("%Y-%m-%d"),
                    "kospi_vol": None, "kosdaq_vol": None, "volume": None, "high": None}
        dates = []
        for f in all_files:
            m = re.search(r'(\d{6})\.(xlsx|csv)$', f, re.I)
            if m:
                try:
                    dates.append(datetime.strptime(m.group(1), "%y%m%d"))
                except:
                    pass
        latest = max(dates).strftime("%Y-%m-%d") if dates else datetime.today().strftime("%Y-%m-%d")
        return find_latest_files(latest)


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────

def _find_any(base: str):
    """xlsx 또는 csv 중 존재하는 파일 반환"""
    for ext in ['.xlsx', '.csv']:
        p = os.path.join(INPUT_DIR, base + ext)
        if os.path.exists(p):
            return p
    return None

def _to_float(val) -> float:
    try:
        s = str(val).replace(",", "").replace("%", "")
        s = re.sub(r'[▲▼↑↓]', '', s).strip()
        return float(s or 0)
    except:
        return 0.0

def _to_int(val) -> int:
    try:
        s = str(val).replace(",", "").strip().lstrip("'")
        return int(float(s or 0))
    except:
        return 0

def _guess_market(ticker: str) -> str:
    if not re.match(r'^\d{6}$', ticker):
        return "ETF"
    # 간단 추정 (완전하지 않음, kospi/kosdaq 분리 파일 사용 시 무관)
    return "KOSPI"
