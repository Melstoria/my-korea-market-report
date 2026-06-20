import sqlite3

def save_trading_volume(conn, date_str, items):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO trading_volume
                (date, rank, ticker, name, market, sector, close, change_pct, volume, amount, market_cap)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (date_str, item["rank"], item["ticker"], item["name"],
                  item["market"], item["sector"], item["close"], item["change_pct"],
                  item["volume"], item["amount"], item["market_cap"]))
            count += 1
        except:
            pass
    conn.commit()
    print(f"[DB] 거래대금 {count}개 저장")

def save_high_price(conn, date_str, items):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO high_price
                (date, ticker, name, market, sector, close, change_pct, high_52w)
                VALUES (?,?,?,?,?,?,?,?)
            """, (date_str, item["ticker"], item["name"], item["market"],
                  item["sector"], item["close"], item["change_pct"], item["high_52w"]))
            count += 1
        except:
            pass
    conn.commit()
    print(f"[DB] 신고가 {count}개 저장")

def save_upper_limit(conn, date_str, items):
    pass