"""KRX Open API 캐시(data/krx)로 하루치 거래대금·신고가·상한가 목록을 만들어 리포트 DB에 넣는다.
영웅문 수동 파일([0184] 거래대금 상위, [0161] 신고가)을 대체한다.

정의
- 거래대금: 시장별 시가총액 1,000억 이상 보통주(거래대금 > 0), 억원 = 원 / 1e8. 순위는 시장 안 거래대금 순, 전일 순위는 직전 거래일 순위.
- 신고가: 당일 장중 고가가 최근 250거래일(당일 포함) 고가의 최댓값 이상인 종목.
          상장 후 250거래일이 안 된 종목은 있는 기간으로 계산하되, 상장 20거래일 미만은 제외한다.
- 전일거래량대비(vol_ratio): 당일 거래량 / 직전 거래일 거래량 (배수).
- 상한가: 등락률 29.5% 이상 30.5% 이하.
Open API 주식 시세에는 ETF·ETN이 없다.
"""
import pandas as pd

from krx_fetch import cached_days, load_day
from parser import classify_sector
from collector import save_trading_volume, save_high_price, save_upper_limit

WINDOW = 250
MIN_HISTORY = 20


MIN_CAP = 1e11  # 시가총액 1,000억 원


def _universe(df: pd.DataFrame) -> pd.DataFrame:
    """영웅문 [0184]와 같은 범위: 시가총액 1,000억 이상 보통주(종목코드 끝자리 0). 2026-06~08 파일로 확인."""
    return df[(df["거래대금"] > 0) & (df["시가총액"] >= MIN_CAP) & df["티커"].str.endswith("0")]


def _volume_rows(df: pd.DataFrame, prev: pd.DataFrame | None, iso: str) -> list[dict]:
    rows = []
    for m, g in _universe(df).groupby("시장"):
        g = g.sort_values("거래대금", ascending=False).reset_index(drop=True)
        prev_rank = {}
        if prev is not None:
            p = _universe(prev)
            p = p[p["시장"] == m].sort_values("거래대금", ascending=False)
            prev_rank = {t: i + 1 for i, t in enumerate(p["티커"])}
        for i, r in g.iterrows():
            rows.append({
                "rank": i + 1, "ticker": r["티커"], "name": r["종목명"], "market": m,
                "sector": classify_sector(r["종목명"]), "close": float(r["종가"]),
                "change_pct": float(r["등락률"]), "volume": int(r["거래량"]),
                "amount": round(r["거래대금"] / 1e8, 2), "market_cap": round(r["시가총액"] / 1e8, 1),
                "prev_rank": prev_rank.get(r["티커"], 0),
            })
    return rows


def build_day(d: str):
    """d: YYYYMMDD. 반환: (거래대금 rows, 신고가 rows, 상한가 rows)"""
    days = cached_days()
    i = days.index(d)
    hist_days = days[max(0, i - WINDOW + 1): i + 1]
    today = load_day(d)
    prev = load_day(days[i - 1]) if i > 0 else None

    hist = pd.concat([load_day(x)[["티커", "고가"]].assign(일=x) for x in hist_days], ignore_index=True)
    hist = hist[hist["고가"] > 0]
    agg = hist.groupby("티커").agg(최고=("고가", "max"), 일수=("일", "nunique"))

    t = today.merge(agg, left_on="티커", right_index=True, how="left")
    if prev is not None:
        t = t.merge(prev[["티커", "거래량"]].rename(columns={"거래량": "전일거래량"}), on="티커", how="left")
    else:
        t["전일거래량"] = pd.NA
    is_high = (t["고가"] > 0) & (t["고가"] >= t["최고"]) & (t["일수"] >= MIN_HISTORY)
    highs = []
    for _, r in t[is_high].iterrows():
        pv = r["전일거래량"]
        ratio = round(r["거래량"] / pv, 2) if pd.notna(pv) and pv > 0 else 1.0
        highs.append({"ticker": r["티커"], "name": r["종목명"], "market": r["시장"],
                      "sector": classify_sector(r["종목명"]), "close": float(r["종가"]),
                      "change_pct": float(r["등락률"]), "high_52w": float(r["최고"]), "vol_ratio": ratio})

    up = t[(t["등락률"] >= 29.5) & (t["등락률"] <= 30.5)]
    uppers = [{"ticker": r["티커"], "name": r["종목명"], "market": r["시장"],
               "sector": classify_sector(r["종목명"]), "close": float(r["종가"])} for _, r in up.iterrows()]
    return _volume_rows(today, prev, d), highs, uppers


def load_into_db(conn, d: str):
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    vol, highs, uppers = build_day(d)
    for tbl in ("trading_volume", "high_price", "upper_limit", "sector_daily"):
        conn.execute(f"DELETE FROM {tbl} WHERE date=?", (iso,))
    conn.commit()
    save_trading_volume(conn, iso, vol)
    save_high_price(conn, iso, highs)
    save_upper_limit(conn, iso, uppers)
    return iso, len(vol), len(highs), len(uppers)
