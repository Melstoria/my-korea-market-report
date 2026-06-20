"""
Korea Market Analysis Engine v3
- KOSPI / KOSDAQ 완전 분리 (섹터, 종목, 레짐, 전략 모두)
- ETF/ETN 통합 제외
- 섹터 강도 스코어 (거래대금 40% + 신고가 30% + 상한가 20% + 모멘텀 10%)
"""

import sqlite3
import json
from datetime import datetime, date
from collections import defaultdict
from db import get_conn

# ── ETF/ETN 제외 키워드 ───────────────────────────────────────────────────────

# ETN만 제외, ETF 유지
ETF_EXCLUDE = [" ETN", "ETN(", "ETN "]

def _is_etf(name: str) -> bool:
    return any(k in name for k in ETF_EXCLUDE)


# ── 정규화 ────────────────────────────────────────────────────────────────────

def _norm(val, max_val):
    if not max_val: return 0
    return min(100.0, val / max_val * 100)

def _sector_score(amt, high, upper, avg_chg, max_amt, max_high, max_upper):
    return round(
        _norm(amt, max_amt) * 0.40 +
        _norm(high, max_high) * 0.30 +
        _norm(upper, max_upper) * 0.20 +
        max(0, min(10, avg_chg)) * 1.0, 2
    )


# ── 섹터 집계 ─────────────────────────────────────────────────────────────────

def aggregate_sectors(conn, date_str: str, market: str = None) -> list[dict]:
    c = conn.cursor()
    mf = f"AND market='{market}'" if market else ""

    c.execute(f"""
        SELECT sector, SUM(amount) total_amount, COUNT(*) stock_count, AVG(change_pct) avg_change
        FROM trading_volume WHERE date=? {mf}
        GROUP BY sector
    """, (date_str,))
    vol = {r["sector"]: dict(r) for r in c.fetchall()}

    c.execute(f"""
        SELECT sector, COUNT(*) cnt FROM high_price WHERE date=? {mf} GROUP BY sector
    """, (date_str,))
    high = {r["sector"]: r["cnt"] for r in c.fetchall()}

    c.execute(f"""
        SELECT sector, COUNT(*) cnt FROM upper_limit WHERE date=? {mf} GROUP BY sector
    """, (date_str,))
    upper = {r["sector"]: r["cnt"] for r in c.fetchall()}

    all_sectors = set(list(vol) + list(high) + list(upper))
    if not all_sectors: return []

    sectors = []
    for s in all_sectors:
        v = vol.get(s, {})
        sectors.append({
            "sector": s,
            "total_amount":   v.get("total_amount") or 0,
            "stock_count":    v.get("stock_count")  or 0,
            "high_count":     high.get(s, 0),
            "upper_count":    upper.get(s, 0),
            "avg_change_pct": v.get("avg_change")   or 0,
        })

    max_amt   = max(s["total_amount"] for s in sectors) or 1
    max_high  = max(s["high_count"]   for s in sectors) or 1
    max_upper = max(s["upper_count"]  for s in sectors) or 1
    total_all = sum(s["total_amount"] for s in sectors) or 1

    for s in sectors:
        s["sector_score"] = _sector_score(
            s["total_amount"], s["high_count"], s["upper_count"],
            s["avg_change_pct"], max_amt, max_high, max_upper
        )
        s["share_pct"] = round(s["total_amount"] / total_all * 100, 1)

    return sorted(sectors, key=lambda x: x["total_amount"], reverse=True)


# ── 이전 거래일 ───────────────────────────────────────────────────────────────

def get_prev_date(conn, date_str: str) -> str | None:
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT date FROM sector_daily WHERE date<? ORDER BY date DESC LIMIT 1
    """, (date_str,))
    r = c.fetchone()
    return r["date"] if r else None


# ── 섹터별 종목 조회 ─────────────────────────────────────────────────────────

def get_sector_stocks(conn, date_str: str, market: str = None) -> dict:
    c = conn.cursor()
    q = "SELECT sector,name,market,amount,change_pct,rank FROM trading_volume WHERE date=?"
    params = [date_str]
    if market:
        q += " AND market=?"
        params.append(market)
    q += " ORDER BY sector, amount DESC"
    c.execute(q, params)
    raw = defaultdict(list)
    for r in c.fetchall():
        if not _is_etf(r["name"]):
            raw[r["sector"]].append(dict(r))
    return {k: v[:10] for k, v in raw.items()}


# ── 거래대금 폭발 배율 ────────────────────────────────────────────────────────

def get_volume_explosion(conn, date_str: str, prev_date: str, market: str = None, top_n=7) -> list[dict]:
    if not prev_date: return []
    c = conn.cursor()

    q = "SELECT ticker,name,market,sector,close,change_pct,amount FROM trading_volume WHERE date=?"
    params = [date_str]
    if market:
        q += " AND market=?"
        params.append(market)
    c.execute(q, params)
    today = {r["ticker"]: dict(r) for r in c.fetchall()}

    c.execute("SELECT ticker,amount FROM trading_volume WHERE date=?", (prev_date,))
    prev = {r["ticker"]: r["amount"] for r in c.fetchall()}

    results = []
    for ticker, t in today.items():
        if _is_etf(t["name"]): continue
        pa = prev.get(ticker, 0)
        if pa > 0:
            t["vol_explosion_ratio"] = round(t["amount"] / pa, 1)
            results.append(t)

    results.sort(key=lambda x: x["vol_explosion_ratio"], reverse=True)
    return results[:top_n]


# ── 시장별 최고 상승 종목 ─────────────────────────────────────────────────────

def get_top_gainers(conn, date_str: str, market: str = None, top_n=7) -> list[dict]:
    c = conn.cursor()
    q = "SELECT name,market,sector,close,change_pct,amount FROM trading_volume WHERE date=? AND change_pct>0"
    params = [date_str]
    if market:
        q += " AND market=?"
        params.append(market)
    q += " ORDER BY change_pct DESC LIMIT 200"
    c.execute(q, params)
    return [dict(r) for r in c.fetchall() if not _is_etf(r["name"])][:top_n]


# ── 거래대금 절대액 TOP (비ETF) ───────────────────────────────────────────────

def get_vol_top(conn, date_str: str, market: str = None, top_n=5) -> list[dict]:
    c = conn.cursor()
    q = "SELECT name,market,sector,close,change_pct,amount,rank FROM trading_volume WHERE date=?"
    params = [date_str]
    if market:
        q += " AND market=?"
        params.append(market)
    q += " ORDER BY amount DESC LIMIT 100"
    c.execute(q, params)
    return [dict(r) for r in c.fetchall() if not _is_etf(r["name"])][:top_n]


# ── 고점수 + 대량거래 ─────────────────────────────────────────────────────────

def get_high_with_volume(conn, date_str: str, market: str = None) -> list[dict]:
    """신고가 + 거래량급증 — trading_volume.market 기준으로 시장 분리 (high_price.market 불완전 보완)"""
    c = conn.cursor()
    mf = f"AND v.market='{market}'" if market else ""
    c.execute(f"""
        SELECT h.ticker, h.name,
               COALESCE(v.market, h.market) AS market,
               h.sector, h.close, h.change_pct,
               h.vol_ratio, v.amount, v.rank AS vol_rank
        FROM high_price h
        INNER JOIN trading_volume v ON h.ticker=v.ticker AND h.date=v.date
        WHERE h.date=? AND h.vol_ratio>=1.2 {mf}
        ORDER BY h.change_pct DESC LIMIT 12
    """, (date_str,))
    ETF_BRD = ["KODEX","TIGER","KBSTAR","ARIRANG","ACE ","SOL ","PLUS ","KOSEF",
                "HANARO","RISE ","TIMEFOLIO","KIWOOM ","1Q "," ETN","ETN(","KoAct","액티브","나스닥","S&P"]
    def _excl(name): return any(k in name for k in ETF_BRD)
    return [dict(r) for r in c.fetchall() if not _excl(r["name"])]


# ── 모멘텀 분류 ──────────────────────────────────────────────────────────────

def classify_momentum(conn, date_str: str, prev_date: str, market: str = None) -> dict:
    if not prev_date:
        return {"sustained": [], "emerging": [], "profit_taking": []}
    c = conn.cursor()

    mf = f"AND market='{market}'" if market else ""
    c.execute(f"""
        SELECT ticker,name,market,sector,close,change_pct,amount,rank
        FROM trading_volume WHERE date=? {mf} ORDER BY rank LIMIT 50
    """, (date_str,))
    today_top = {r["ticker"]: dict(r) for r in c.fetchall()}

    c.execute(f"""
        SELECT ticker,name,change_pct,amount,rank
        FROM trading_volume WHERE date=? {mf} ORDER BY rank LIMIT 50
    """, (prev_date,))
    prev_top = {r["ticker"]: dict(r) for r in c.fetchall()}

    sustained, emerging, profit_taking = [], [], []
    for ticker, t in today_top.items():
        if _is_etf(t["name"]): continue
        if ticker in prev_top:
            p = prev_top[ticker]
            if t["change_pct"] > 1:
                sustained.append({**t, "prev_rank": p["rank"]})
            elif t["change_pct"] < -2:
                profit_taking.append({**t, "prev_rank": p["rank"]})
        else:
            if t["change_pct"] > 3 or t["amount"] > 500:
                emerging.append(t)

    return {
        "sustained":     sorted(sustained, key=lambda x: x["amount"], reverse=True)[:6],
        "emerging":      sorted(emerging,  key=lambda x: x["change_pct"], reverse=True)[:6],
        "profit_taking": sorted(profit_taking, key=lambda x: x["change_pct"])[:5],
    }


# ── 순환매 탐지 ──────────────────────────────────────────────────────────────

def detect_rotation(conn, date_str: str) -> dict:
    c = conn.cursor()
    c.execute("""
        SELECT date,sector,sector_score FROM sector_daily
        WHERE date<=? ORDER BY date DESC LIMIT 80
    """, (date_str,))
    rows = c.fetchall()
    if not rows:
        return {"signal": "데이터 부족", "detail": ""}

    date_data = defaultdict(dict)
    dates = []
    for r in rows:
        date_data[r["date"]][r["sector"]] = r["sector_score"]
        if r["date"] not in dates: dates.append(r["date"])

    dates = sorted(dates, reverse=True)[:5]
    if len(dates) < 2:
        return {"signal": "관망", "detail": "비교 데이터 부족"}

    today_s, prev_s = date_data[dates[0]], date_data[dates[1]]
    rising  = [(s, sc - prev_s.get(s,0)) for s,sc in today_s.items() if sc-prev_s.get(s,0)>=5]
    falling = [(s, sc - prev_s.get(s,0)) for s,sc in today_s.items() if sc-prev_s.get(s,0)<=-5]
    rising.sort(key=lambda x: x[1], reverse=True)
    falling.sort(key=lambda x: x[1])

    if rising and falling:
        top_y = max(prev_s.items(), key=lambda x: x[1])[0] if prev_s else ""
        top_t = max(today_s.items(), key=lambda x: x[1])[0] if today_s else ""
        signal = f"⚡ 섹터 교체 — {top_y} → {top_t}" if top_y!=top_t else \
                 f"🔄 부분 순환매 — {', '.join(r[0] for r in rising[:2])} 부상"
    elif rising:
        signal = f"📈 집중 강화 — {', '.join(r[0] for r in rising[:2])}"
    elif falling:
        signal = f"📉 섹터 약화 — {', '.join(f[0] for f in falling[:2])}"
    else:
        signal = "➡️ 중립"

    parts = []
    if rising:  parts.append("부상: " + ", ".join(f"{s}(+{c:.1f}p)" for s,c in rising[:3]))
    if falling: parts.append("약화: " + ", ".join(f"{s}({c:.1f}p)" for s,c in falling[:3]))
    return {"signal": signal, "detail": " / ".join(parts)}


# ── 시장 레짐 ────────────────────────────────────────────────────────────────

def detect_market_regime(sectors: list[dict], high_total: int, upper_total: int,
                          top_stocks: list[dict], market_label: str = "") -> dict:
    """
    시장 색깔 키워드 — 해당 시장(KOSPI/KOSDAQ)의 그날 분위기를 태그로 요약
    인버스/ETF 관련 태그 없음. 순수 시장 흐름만.
    """
    tags, explanations = [], []
    non_etc = [s for s in sectors if s["sector"] != "기타"]
    is_kosdaq = market_label == "KOSDAQ"

    # ── 주도섹터 집중도
    if non_etc:
        top1 = non_etc[0]
        share = top1.get("share_pct", 0) or (top1["total_amount"] / max(sum(s["total_amount"] for s in non_etc),1) * 100)
        s1 = top1["sector"]
        if share >= 45:
            tags.append(f"{s1} 독주")
            explanations.append(f"{s1}에 자금 {share:.0f}% 집중.")
        elif share >= 28:
            tags.append(f"{s1} 주도")
            explanations.append(f"{s1} 중심 장세 ({share:.0f}%).")
        else:
            tags.append("자금 분산")
            explanations.append("특정 섹터 쏠림 없이 자금 분산.")

    # ── 시장 강도 (상한가 기준)
    if upper_total >= 30:
        tags.append("전방위 강세")
        explanations.append(f"상한가 {upper_total}개, 광범위 매수.")
    elif upper_total >= 15:
        tags.append("강세 기류")
        explanations.append(f"상한가 {upper_total}개.")
    elif upper_total >= 5:
        tags.append("온건 강세")
    elif upper_total == 0:
        tags.append("관망 장세")
        explanations.append("상한가 없음. 매수 에너지 소강.")

    # ── 신고가 확산
    if high_total >= 60:
        tags.append("신고가 러시")
        explanations.append(f"신고가 {high_total}개 — 추세 강화.")
    elif high_total >= 25:
        tags.append("신고가 확산")
        explanations.append(f"신고가 {high_total}개.")

    # ── 섹터 테마 키워드 (상위 5개 섹터 기준)
    top5_sectors = [s["sector"] for s in non_etc[:5]]
    if "반도체/하드웨어" in top5_sectors and "반도체 장비/소부장" in top5_sectors:
        tags.append("반도체 밸류체인 동반")
        explanations.append("반도체 완성품·장비·소부장 동시 강세.")
    if "자동차/부품" in top5_sectors and "로보틱스/자동화" in top5_sectors:
        tags.append("제조업 리레이팅")
        explanations.append("자동차·로보틱스 동반 자금 유입.")
    if "방산/우주" in top5_sectors:
        tags.append("방산·우주 테마")
    if "바이오/헬스케어" in top5_sectors and is_kosdaq:
        tags.append("바이오 수급 유입")
        explanations.append("코스닥 바이오 섹터 자금 재유입.")
    if "2차전지/소재" in top5_sectors:
        tags.append("2차전지 반등")
    if len(non_etc) >= 2:
        # 2위 섹터가 1위 대비 50% 이상이면 순환매 신호
        ratio = non_etc[1]["total_amount"] / max(non_etc[0]["total_amount"], 1)
        if ratio >= 0.6:
            tags.append("순환매 감지")
            explanations.append(f"{non_etc[0]['sector']}→{non_etc[1]['sector']} 순환 조짐.")

    # ── 코스닥 특화
    if is_kosdaq:
        top_gainer_pct = max((s.get("avg_change_pct",0) for s in non_etc[:3]), default=0)
        if top_gainer_pct >= 5:
            tags.append("단타 열기")
            explanations.append("상위 섹터 평균 등락 높음, 단기 매수세 강함.")

    if not tags: tags = ["중립"]
    if not explanations: explanations = ["뚜렷한 방향성 없음."]
    return {"tags": tags, "explanation": " ".join(explanations)}


# ── 시간 지평 전략 ────────────────────────────────────────────────────────────

def generate_strategy(sectors: list[dict], momentum: dict, market_label: str = "") -> dict:
    top3     = [s["sector"] for s in sectors if s["sector"] != "기타"][:3]
    top1     = top3[0] if top3 else ""
    top2str  = ", ".join(top3[:2]) if len(top3) >= 2 else top1
    sustained = [s["name"] for s in momentum.get("sustained", [])[:5]]
    emerging  = [s["name"] for s in momentum.get("emerging",  [])[:5]]
    is_kospi  = market_label == "KOSPI"
    is_kosdaq = market_label == "KOSDAQ"

    if is_kospi:
        short = {
            "title": "단기 (1~5일)", "stance": "대형주 모멘텀 추종",
            "stocks": sustained[:4],
            "points": [
                f"주도섹터 {top1} 거래대금 상위 대형주 단기 트레이딩",
                "외국인·기관 동반 순매수 종목 우선 접근",
                "시총 상위 모멘텀 종목 눌림목 매수 집중",
            ]
        }
        mid = {
            "title": "중기 (1~3개월)", "stance": "섹터 로테이션 + 실적주",
            "stocks": top3[:3],
            "points": [
                f"신고가 돌파한 {top2str} 대형주 비중 점진 확대",
                "주도섹터 교체 시 2위 섹터로 선제 이동",
                "외국인 순매수 누적 종목 중기 홀딩 유지",
            ]
        }
        long = {
            "title": "장기 (6개월+)", "stance": "수출 대형주 구조적 보유",
            "stocks": [],
            "points": [
                "반도체·자동차·방산 수출 대형주 장기 핵심 포지션 유지",
                "PER 10배 이하 대형 수출주 구간별 분할 적립",
                "배당성장 + 자사주 소각 기업 복리 수익 극대화",
            ]
        }
    elif is_kosdaq:
        short = {
            "title": "단기 (1~5일)", "stance": "테마·중소형 단타",
            "stocks": (emerging or sustained)[:4],
            "points": [
                f"주도섹터 {top1} 내 거래대금 급증 중소형주 단기 포착",
                "거래량 전일비 3배 이상 + 상승 종목 우선 진입",
                "급등 당일 모멘텀 집중, 익일 눌림 재진입은 선별적으로",
            ]
        }
        mid = {
            "title": "중기 (1~3개월)", "stance": "테마 선점 + 실적 중소형",
            "stocks": top3[:3],
            "points": [
                f"{top2str} 테마 내 영업이익 턴어라운드 중소형주 선별 보유",
                "단순 테마 편승보다 실적 가시성 있는 종목 집중",
                "섹터 자금 이탈 신호 시 빠른 비중 축소",
            ]
        }
        long = {
            "title": "장기 (6개월+)", "stance": "바이오·AI 구조적 성장",
            "stocks": [],
            "points": [
                "임상 후기 또는 기술수출 가시화 바이오 종목 장기 보유",
                "AI·로보틱스·반도체 장비 구조적 성장 중소형 선별 적립",
                "핵심 성장 테마는 변동성에도 포지션 일부 유지",
            ]
        }
    else:
        short = {
            "title": "단기 (1~5일)", "stance": "모멘텀 추종", "stocks": sustained[:4],
            "points": [f"주도섹터 {top1} 거래 상위 종목 단기 트레이딩",
                       "거래량 급증 신규 부각 종목 선별 진입",
                       "지속형 종목 눌림목 매수 관점 유지"]
        }
        mid = {
            "title": "중기 (1~3개월)", "stance": "섹터 로테이션 대응", "stocks": top3[:3],
            "points": [f"신고가 동반 {top2str} 종목 비중 유지",
                       "주도섹터 교체 신호 시 선제적 리밸런싱",
                       "2~3위 섹터 점진적 비중 확대"]
        }
        long = {
            "title": "장기 (6개월+)", "stance": "구조적 성장 집중", "stocks": [],
            "points": ["AI·반도체·방산 구조적 수혜 핵심 보유",
                       "밸류에이션 부담 없는 수출형 대형주 적립",
                       "이익 성장 가시성 높은 종목 장기 보유"]
        }

    return {"short": short, "mid": mid, "long": long}


def save_sector_daily(conn, date_str: str, sectors: list[dict]):
    for s in sectors:
        conn.execute("""
            INSERT OR REPLACE INTO sector_daily
            (date,sector,total_amount,stock_count,high_count,upper_count,avg_change_pct,sector_score)
            VALUES (?,?,?,?,?,?,?,?)
        """, (date_str, s["sector"], s["total_amount"], s["stock_count"],
              s["high_count"], s["upper_count"], s["avg_change_pct"], s["sector_score"]))
    conn.commit()


def _get_high_stocks(c, date_str: str, market: str) -> list[dict]:
    """신고가 종목 전체 리스트 (ETF 제외, 거래대금 내림차순)"""
    ETF_BRD = ["KODEX","TIGER","KBSTAR","ARIRANG","ACE ","SOL ","PLUS ","KOSEF",
               "HANARO","RISE ","TIMEFOLIO","KIWOOM ","1Q "," ETN","ETN(","KoAct","액티브"]
    c.execute("""
        SELECT h.name, h.sector, h.change_pct, h.vol_ratio, COALESCE(v.amount,0) AS amount
        FROM high_price h
        LEFT JOIN trading_volume v ON h.ticker=v.ticker AND h.date=v.date
        WHERE h.date=? AND h.market=?
        ORDER BY COALESCE(v.amount,0) DESC
    """, (date_str, market))
    return [dict(r) for r in c.fetchall()
            if not any(k in r["name"] for k in ETF_BRD)]

# ── 전체 분석 실행 ────────────────────────────────────────────────────────────

def run_analysis(target_date: str = None) -> dict:
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n[Analysis] {target_date} 분석 시작")
    conn = get_conn()
    c = conn.cursor()

    # 시장 구분 확인
    c.execute("SELECT DISTINCT market FROM trading_volume WHERE date=?", (target_date,))
    markets = [r["market"] for r in c.fetchall()]
    has_split = "KOSPI" in markets and "KOSDAQ" in markets

    prev_date = get_prev_date(conn, target_date)

    # ── 섹터 집계 (전체 / KOSPI / KOSDAQ)
    sectors_all    = aggregate_sectors(conn, target_date)
    sectors_kospi  = aggregate_sectors(conn, target_date, "KOSPI")  if has_split else sectors_all
    sectors_kosdaq = aggregate_sectors(conn, target_date, "KOSDAQ") if has_split else []
    save_sector_daily(conn, target_date, sectors_all)

    # ── 섹터별 종목
    sector_stocks        = get_sector_stocks(conn, target_date)
    sector_stocks_kospi  = get_sector_stocks(conn, target_date, "KOSPI")  if has_split else sector_stocks
    sector_stocks_kosdaq = get_sector_stocks(conn, target_date, "KOSDAQ") if has_split else {}

    # ── 폭발 배율 (시장별)
    explosion        = get_volume_explosion(conn, target_date, prev_date)
    explosion_kospi  = get_volume_explosion(conn, target_date, prev_date, "KOSPI")  if has_split else explosion
    explosion_kosdaq = get_volume_explosion(conn, target_date, prev_date, "KOSDAQ") if has_split else []

    # ── 최고 상승 (시장별)
    gainers_kospi  = get_top_gainers(conn, target_date, "KOSPI")  if has_split else get_top_gainers(conn, target_date)
    gainers_kosdaq = get_top_gainers(conn, target_date, "KOSDAQ") if has_split else []

    # ── 거래대금 절대액 TOP5 (시장별)
    vol_top5        = get_vol_top(conn, target_date)
    vol_top5_kospi  = get_vol_top(conn, target_date, "KOSPI")  if has_split else vol_top5
    vol_top5_kosdaq = get_vol_top(conn, target_date, "KOSDAQ") if has_split else []

    # ── 고점수 + 대량거래 (시장별)
    high_vol        = get_high_with_volume(conn, target_date)
    high_vol_kospi  = get_high_with_volume(conn, target_date, "KOSPI")  if has_split else high_vol
    high_vol_kosdaq = get_high_with_volume(conn, target_date, "KOSDAQ") if has_split else []

    # ── 모멘텀 분류 (시장별)
    momentum_kospi  = classify_momentum(conn, target_date, prev_date, "KOSPI")  if has_split else classify_momentum(conn, target_date, prev_date)
    momentum_kosdaq = classify_momentum(conn, target_date, prev_date, "KOSDAQ") if has_split else {"sustained":[],"emerging":[],"profit_taking":[]}

    # ── 레짐 (시장별)
    c.execute("SELECT name,market,amount FROM trading_volume WHERE date=? ORDER BY amount DESC LIMIT 50", (target_date,))
    top_stocks_all = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) n FROM high_price WHERE date=?",   (target_date,)); high_total  = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) n FROM upper_limit WHERE date=?",  (target_date,)); upper_total = c.fetchone()["n"]

    # 시장별 신고가/상한가 수 — 레짐 신호 분리용
    c.execute("SELECT COUNT(*) n FROM high_price WHERE date=? AND market='KOSPI'",  (target_date,)); high_kospi  = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) n FROM high_price WHERE date=? AND market='KOSDAQ'", (target_date,)); high_kosdaq = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) n FROM upper_limit WHERE date=? AND market='KOSPI'",  (target_date,)); upper_kospi  = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) n FROM upper_limit WHERE date=? AND market='KOSDAQ'", (target_date,)); upper_kosdaq = c.fetchone()["n"]
    # high_price는 market 추정이 불완전하므로 KOSPI/KOSDAQ 합이 0이면 전체값 분배
    if high_kospi + high_kosdaq == 0:
        high_kospi = high_kosdaq = high_total // 2

    regime_kospi  = detect_market_regime(sectors_kospi,  high_kospi,  upper_kospi,  top_stocks_all, "KOSPI")
    regime_kosdaq = detect_market_regime(sectors_kosdaq, high_kosdaq, upper_kosdaq, top_stocks_all, "KOSDAQ")

    # ── 전략 (시장별)
    strategy_kospi  = generate_strategy(sectors_kospi,  momentum_kospi,  "KOSPI")
    strategy_kosdaq = generate_strategy(sectors_kosdaq, momentum_kosdaq, "KOSDAQ")

    # ── 순환매
    rotation = detect_rotation(conn, target_date)

    # ── 요약 수치
    c.execute("SELECT SUM(amount) s FROM trading_volume WHERE date=? AND market='KOSPI'",  (target_date,)); kospi_total  = c.fetchone()["s"] or 0
    c.execute("SELECT SUM(amount) s FROM trading_volume WHERE date=? AND market='KOSDAQ'", (target_date,)); kosdaq_total = c.fetchone()["s"] or 0

    # 신고가 종목 리스트 (conn.close 전에 쿼리)
    high_stocks_kospi_list  = _get_high_stocks(c, target_date, "KOSPI")
    high_stocks_kosdaq_list = _get_high_stocks(c, target_date, "KOSDAQ")

    conn.close()

    result = {
        "date": target_date, "prev_date": prev_date, "has_split": has_split,
        # 섹터
        "sectors": sectors_all, "sectors_kospi": sectors_kospi, "sectors_kosdaq": sectors_kosdaq,
        # 섹터별 종목
        "sector_stocks": sector_stocks, "sector_stocks_kospi": sector_stocks_kospi, "sector_stocks_kosdaq": sector_stocks_kosdaq,
        # 거래대금 합계
        "total_amount": kospi_total + kosdaq_total, "kospi_total": kospi_total, "kosdaq_total": kosdaq_total,
        "high_total": high_total, "upper_total": upper_total, "high_kospi": high_kospi, "high_kosdaq": high_kosdaq,
        "high_stocks_kospi":  high_stocks_kospi_list,
        "high_stocks_kosdaq": high_stocks_kosdaq_list,
        # 4개 박스 (시장별)
        "explosion_kospi":  explosion_kospi,  "explosion_kosdaq":  explosion_kosdaq,
        "gainers_kospi":    gainers_kospi,     "gainers_kosdaq":    gainers_kosdaq,
        "vol_top5_kospi":   vol_top5_kospi,    "vol_top5_kosdaq":   vol_top5_kosdaq,
        "high_vol_kospi":   high_vol_kospi,    "high_vol_kosdaq":   high_vol_kosdaq,
        # 레짐 / 전략 (시장별)
        "regime_kospi":   regime_kospi,   "regime_kosdaq":   regime_kosdaq,
        "strategy_kospi": strategy_kospi, "strategy_kosdaq": strategy_kosdaq,
        # 순환매 (공통)
        "rotation": rotation,
        # 하위호환
        "sectors_all": sectors_all, "explosion": explosion_kospi,
        "high_stocks": [], "top_stocks": top_stocks_all,
        "leading_sectors": sectors_all[:5],
    }

    print(f"[Analysis] 완료 — KOSPI 주도: {[s['sector'] for s in sectors_kospi[:3] if s['sector']!='기타']}")
    print(f"[Analysis]         KOSDAQ 주도: {[s['sector'] for s in sectors_kosdaq[:3] if s['sector']!='기타']}")
    return result


if __name__ == "__main__":
    r = run_analysis()
    if r:
        print(f"KOSPI {r['kospi_total']:,.0f}억 / KOSDAQ {r['kosdaq_total']:,.0f}억")
