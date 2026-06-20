import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(os.getcwd(), "docs", "reports")
DB_PATH = os.path.join(os.getcwd(), "data", "korea_market.db")
INPUT_DIR = os.path.join(os.getcwd(), "data", "input")

os.environ["DB_PATH"] = DB_PATH
os.environ["OUTPUT_DIR"] = OUTPUT_DIR
os.environ["INPUT_DIR"] = INPUT_DIR

from db import init_db, get_conn
from parser import find_latest_files, parse_volume, parse_high, parse_date_from_filename
from collector import save_trading_volume, save_high_price
from analyzer import run_analysis
from reporter import generate_report
from update_index import update_index

def run_pipeline(target_date=None):
    vol_file, high_file = find_latest_files(target_date)
    if not vol_file and not high_file:
        print("data/input/ 폴더에 파일이 없습니다.")
        return

    ref_file = vol_file or high_file
    date_str = parse_date_from_filename(ref_file)
    print(f"\n{'='*50}")
    print(f"  My Korea Market Report: {date_str}")
    print(f"{'='*50}\n")

    init_db()
    conn = get_conn()

    if vol_file:
        print(f"[1] 거래대금: {os.path.basename(vol_file)}")
        save_trading_volume(conn, date_str, parse_volume(vol_file))

    if high_file:
        print(f"[2] 신고가: {os.path.basename(high_file)}")
        save_high_price(conn, date_str, parse_high(high_file))

    conn.close()

    print("\n[3] 섹터 분석 중...")
    analysis = run_analysis(date_str)
    if not analysis:
        print("분석 실패")
        return

    print(f"    주도섹터: {[s['sector'] for s in analysis['leading_sectors'][:3]]}")

    print("\n[4] 리포트 생성 중...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = generate_report(analysis, OUTPUT_DIR)
    update_index()

    print(f"\n✅ 완료: {filepath}")
    return filepath

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(target)