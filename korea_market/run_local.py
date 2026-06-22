"""
run_local.py — 매일 실행하는 메인 파이프라인

파일명 규칙 (data/input/ 폴더):
  [권장] volume_kospi_YYMMDD.xlsx   → KOSPI 거래대금 (영웅문 [0184] KOSPI 필터)
         volume_kosdaq_YYMMDD.xlsx  → KOSDAQ 거래대금 (영웅문 [0184] KOSDAQ 필터)
  [대안] volume_YYMMDD.xlsx         → KOSPI+KOSDAQ 통합 (구버전 호환)
         high_YYMMDD.xlsx           → 신고가 (영웅문 [0161])
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --input 인자로 경로 지정 가능, 없으면 기본 경로 사용
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(_base, "docs", "reports")
DB_PATH    = os.path.join(_base, "data", "korea_market.db")

if "--input" in sys.argv:
    INPUT_DIR = sys.argv[sys.argv.index("--input") + 1]
else:
    INPUT_DIR = r"C:\Users\User\Desktop\project\find_leader_csv\korea"

os.environ["DB_PATH"]    = DB_PATH
os.environ["OUTPUT_DIR"] = OUTPUT_DIR
os.environ["INPUT_DIR"]  = INPUT_DIR

from db       import init_db, get_conn
from parser   import find_latest_files, parse_volume, parse_high, parse_date_from_filename
from collector import save_trading_volume, save_high_price
from analyzer  import run_analysis
from reporter  import generate_report
from update_index import update_index

def run_pipeline(target_date=None):
    files = find_latest_files(target_date)
    date_str = files["date"]

    print(f"\n{'='*52}")
    print(f"  My Korea Market Report: {date_str}")
    print(f"{'='*52}\n")

    init_db()
    conn = get_conn()

    # KOSPI 거래대금
    if files.get("kospi_vol"):
        print(f"[1a] KOSPI 거래대금: {os.path.basename(files['kospi_vol'])}")
        save_trading_volume(conn, date_str, parse_volume(files["kospi_vol"], "KOSPI"))

    # KOSDAQ 거래대금
    if files.get("kosdaq_vol"):
        print(f"[1b] KOSDAQ 거래대금: {os.path.basename(files['kosdaq_vol'])}")
        save_trading_volume(conn, date_str, parse_volume(files["kosdaq_vol"], "KOSDAQ"))

    # 통합 거래대금 (구버전)
    if files.get("volume") and not files.get("kospi_vol") and not files.get("kosdaq_vol"):
        print(f"[1] 거래대금(통합): {os.path.basename(files['volume'])}")
        save_trading_volume(conn, date_str, parse_volume(files["volume"]))

    # 신고가
    # 신고가 — 분리 파일 우선(high_kospi_YYMMDD, high_kosdaq_YYMMDD), 없으면 통합
    if files.get("high_kospi"):
        print(f"[2a] 신고가(KOSPI): {os.path.basename(files['high_kospi'])}")
        highs = parse_high(files["high_kospi"])
        for h in highs: h["market"] = "KOSPI"
        save_high_price(conn, date_str, highs)
    if files.get("high_kosdaq"):
        print(f"[2b] 신고가(KOSDAQ): {os.path.basename(files['high_kosdaq'])}")
        highs = parse_high(files["high_kosdaq"])
        for h in highs: h["market"] = "KOSDAQ"
        save_high_price(conn, date_str, highs)
    if not files.get("high_kospi") and not files.get("high_kosdaq") and files.get("high"):
        print(f"[2] 신고가(통합): {os.path.basename(files['high'])}")
        save_high_price(conn, date_str, parse_high(files["high"]))

    conn.close()

    print("\n[3] 섹터 분석 중...")
    analysis = run_analysis(date_str)
    if not analysis:
        print("❌ 분석 실패 — 데이터를 확인하세요")
        return

    print(f"    주도섹터: {[s['sector'] for s in analysis['leading_sectors'][:3]]}")
    print(f"    레짐: {', '.join(analysis.get('regime_kospi',{}).get('tags',[''])[:2])}")

    print("\n[4] 리포트 생성 중...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = generate_report(analysis, OUTPUT_DIR)
    update_index()

    print(f"\n✅ 완료: {filepath}")
    return filepath

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != INPUT_DIR]
    target = args[0] if args else None
    run_pipeline(target)