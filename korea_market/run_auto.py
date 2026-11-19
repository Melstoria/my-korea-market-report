"""일간 리포트 자동 실행(영웅문 수동 파일 대신 KRX Open API).

순서: Open API로 어제까지 수집 → 아직 리포트가 없는 거래일마다 DB 적재 → 분석 → 리포트 HTML → 허브 목록 갱신.
게시(git push)는 하지 않는다. 게시는 publish_daily.py가 맡는다.

사용법:
  python run_auto.py                  # 마지막 리포트 다음 거래일부터 어제까지
  python run_auto.py --from 20260821  # 지정일부터 다시 생성(백필)
  python run_auto.py --no-fetch ...   # 수집 생략
"""
import os, sys, glob, re
from datetime import date, timedelta

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["DB_PATH"] = os.path.join(_base, "data", "korea_market.db")
os.environ["OUTPUT_DIR"] = os.path.join(_base, "docs", "reports")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from db import init_db, get_conn
from krx_fetch import cached_days, fetch
from krx_build import load_into_db
from analyzer import run_analysis
from reporter import generate_report
from update_index import update_index

SOURCE_NOTE = "KRX Open API 기준 · KRX 거래만(NXT 제외, 2026-08-20 이전 리포트는 NXT 포함) · ETF·ETN 제외"
MIN_ROWS = 900  # 두 시장 합계 종목 수(시총 1,000억 이상 보통주, 평소 약 1,300)가 이보다 적으면 이상으로 보고 중단


def last_report_day() -> str | None:
    files = glob.glob(os.path.join(os.environ["OUTPUT_DIR"], "korea_daily_report_*.html"))
    ds = [re.search(r"(\d{8})\.html$", f).group(1) for f in files]
    return max(ds) if ds else None


def main():
    args = sys.argv[1:]
    if "--no-fetch" not in args:
        days = cached_days()
        start = (pd.Timestamp(days[-1]) + pd.Timedelta(days=1)).strftime("%Y%m%d") if days else "20250801"
        fetch(start, (date.today() - timedelta(days=1)).strftime("%Y%m%d"))
    if "--from" in args:
        start = args[args.index("--from") + 1]
    else:
        last = last_report_day()
        start = (pd.Timestamp(last) + pd.Timedelta(days=1)).strftime("%Y%m%d") if last else cached_days()[-1]
    targets = [d for d in cached_days() if d >= start]
    if not targets:
        print("새 거래일 없음: 리포트 생략")
        return
    init_db()
    made = []
    for d in targets:
        conn = get_conn()
        iso, nv, nh, nu = load_into_db(conn, d)
        conn.close()
        print(f"[{iso}] 거래대금 {nv}종목 · 신고가 {nh} · 상한가 {nu}")
        if nv < MIN_ROWS:
            sys.exit(f"{iso} 종목 수 {nv} < {MIN_ROWS}: 데이터 이상, 중단")
        analysis = run_analysis(iso)
        analysis["source_note"] = SOURCE_NOTE
        made.append(generate_report(analysis, os.environ["OUTPUT_DIR"]))
    update_index()
    print("생성:", len(made), "개 /", os.path.basename(made[0]), "~", os.path.basename(made[-1]))


if __name__ == "__main__":
    main()
