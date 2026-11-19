"""KRX Open API(공식)로 유가증권·코스닥 종목별 일별 시세를 받아 data/krx/YYYYMMDD_{KOSPI,KOSDAQ}.csv로 캐시한다.

- 키: 저장소 밖 .env의 KRX_API_KEY (값은 출력하지 않음). 경로는 KRX_ENV_PATH 환경변수로 바꿀 수 있다.
- Open API는 다음 날(D+1) 데이터를 제공한다. 오늘 날짜는 조회하지 않는다.
- 응답이 비면 휴장일로 보고 건너뛴다. 한 시장만 응답하면 중단한다.
- 사용법:
    python krx_fetch.py                 # 마지막 캐시 다음 날부터 어제까지
    python krx_fetch.py 20250801 20251031  # 지정 구간(이미 있는 날은 건너뜀)
"""
import os, sys, time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "krx"
ENV = Path(os.environ.get("KRX_ENV_PATH",
           r"C:\Users\User\Desktop\20_프로젝트\project\krx_market_bottom\market-bottom\market-bottom\.env"))
EP = {"KOSPI": "stk_bydd_trd", "KOSDAQ": "ksq_bydd_trd"}
COLS = {"ISU_CD": "티커", "ISU_NM": "종목명", "SECT_TP_NM": "소속부", "TDD_OPNPRC": "시가", "TDD_HGPRC": "고가",
        "TDD_LWPRC": "저가", "TDD_CLSPRC": "종가", "ACC_TRDVOL": "거래량", "ACC_TRDVAL": "거래대금",
        "FLUC_RT": "등락률", "MKTCAP": "시가총액", "LIST_SHRS": "상장주식수"}
NUM = ["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률", "시가총액", "상장주식수"]


def _key():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("KRX_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("KRX_API_KEY 없음(.env 확인)")


def cached_days():
    return sorted({p.name[:8] for p in CACHE.glob("*_KOSPI.csv") if (CACHE / f"{p.name[:8]}_KOSDAQ.csv").exists()})


def load_day(d: str) -> pd.DataFrame:
    """두 시장을 합쳐 반환(시장 열 포함). 티커는 문자열."""
    parts = []
    for m in EP:
        df = pd.read_csv(CACHE / f"{d}_{m}.csv", dtype={"티커": str}, encoding="utf-8-sig")
        df["시장"] = m
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def _get(key, ep, d):
    for _ in range(3):
        try:
            r = requests.get(f"https://data-dbg.krx.co.kr/svc/apis/sto/{ep}", params={"basDd": d},
                             headers={"AUTH_KEY": key}, timeout=30)
            r.raise_for_status()
            return r.json().get("OutBlock_1") or []
        except Exception as e:  # 값(키)은 출력하지 않는다
            print("재시도", ep, d, type(e).__name__, flush=True)
            time.sleep(5)
    sys.exit(f"Open API 실패: {ep} {d}")


def fetch(start: str, end: str) -> list[str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    have = set(cached_days())
    yesterday = date.today() - timedelta(days=1)
    days = [x.strftime("%Y%m%d") for x in pd.bdate_range(start, end) if x.date() <= yesterday]
    todo = [d for d in days if d not in have]
    if not todo:
        return []
    key = _key()
    added = []
    for d in todo:
        got = {}
        for m, ep in EP.items():
            rows = _get(key, ep, d)
            time.sleep(0.4)
            if rows:
                got[m] = rows
        if not got:
            print("휴장 또는 미집계:", d, flush=True)
            continue
        if len(got) != 2:
            sys.exit(f"{d} 한쪽 시장만 응답: 중단")
        for m, rows in got.items():
            df = pd.DataFrame(rows)[list(COLS)].rename(columns=COLS)
            for c in NUM:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
            df.to_csv(CACHE / f"{d}_{m}.csv", index=False, encoding="utf-8-sig")
        added.append(d)
    print("추가 거래일:", len(added), added[:3], "..." if len(added) > 3 else "", flush=True)
    return added


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2:
        fetch(a[0], a[1])
    else:
        days = cached_days()
        if not days:
            sys.exit("캐시 없음: 시작·끝 날짜를 지정하세요")
        start = (pd.Timestamp(days[-1]) + pd.DateOffset(days=1)).strftime("%Y%m%d")
        fetch(start, (date.today() - timedelta(days=1)).strftime("%Y%m%d"))
