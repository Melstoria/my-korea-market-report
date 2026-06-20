"""
Korea Market Collector — DB 저장 레이어
신고가 저장 시 trading_volume JOIN으로 market 정확히 채움
"""
import sqlite3

def save_trading_volume(conn: sqlite3.Connection, date_str: str, stocks: list[dict]):
    for s in stocks:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO trading_volume
                (date, rank, ticker, name, market, sector, close, change_pct, volume, amount, market_cap, prev_rank)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                date_str, s["rank"], s["ticker"], s["name"],
                s.get("market",""), s.get("sector","기타"),
                s.get("close",0), s.get("change_pct",0),
                s.get("volume",0), s.get("amount",0), s.get("market_cap",0),
                s.get("prev_rank",0),
            ))
        except:
            pass
    conn.commit()
    print(f"[DB] 거래대금 {len(stocks)}개 저장")

def save_high_price(conn: sqlite3.Connection, date_str: str, stocks: list[dict]):
    # 먼저 저장
    for s in stocks:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO high_price
                (date, ticker, name, market, sector, close, change_pct, high_52w, vol_ratio)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                date_str, s["ticker"], s["name"],
                s.get("market",""), s.get("sector","기타"),
                s.get("close",0), s.get("change_pct",0),
                s.get("high_52w",0), s.get("vol_ratio",1),
            ))
        except:
            pass
    conn.commit()

    # trading_volume JOIN으로 market 정확히 업데이트
    conn.execute("""
        UPDATE high_price
        SET market = (
            SELECT v.market FROM trading_volume v
            WHERE v.ticker = high_price.ticker AND v.date = high_price.date
            LIMIT 1
        )
        WHERE date = ?
        AND EXISTS (
            SELECT 1 FROM trading_volume v
            WHERE v.ticker = high_price.ticker AND v.date = high_price.date
        )
    """, (date_str,))
    conn.commit()

    # market이 여전히 비어있으면 KOSPI 기본값 (영웅문 신고가는 대부분 KOSPI 포함)
    conn.execute("""
        UPDATE high_price SET market = 'KOSPI'
        WHERE date = ? AND (market = '' OR market IS NULL)
    """, (date_str,))
    conn.commit()

    # 결과 확인
    c = conn.cursor()
    c.execute("SELECT market, COUNT(*) n FROM high_price WHERE date=? GROUP BY market", (date_str,))
    breakdown = {r["market"]: r["n"] for r in c.fetchall()}
    total = sum(breakdown.values())
    print(f"[DB] 신고가 {total}개 저장 — {breakdown}")

def save_upper_limit(conn: sqlite3.Connection, date_str: str, stocks: list[dict]):
    for s in stocks:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO upper_limit
                (date, ticker, name, market, sector, close)
                VALUES (?,?,?,?,?,?)
            """, (
                date_str, s["ticker"], s["name"],
                s.get("market",""), s.get("sector","기타"), s.get("close",0),
            ))
        except:
            pass
    conn.commit()
