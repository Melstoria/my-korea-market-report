"""검증용: 예전 영웅문 수동 파일과 Open API로 만든 목록을 같은 날짜끼리 비교한다(DB는 건드리지 않음).
사용법: python validate_vs_manual.py <영웅문 폴더>"""
import os, sys, glob, re
import pandas as pd
from krx_fetch import cached_days
from krx_build import build_day

src = sys.argv[1]
def rd(p):
    df = pd.read_csv(p, encoding="cp949", dtype=str)
    df["티커"] = df["종목코드"].str.lstrip("'").str.zfill(6)
    return df
def num(s): return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("%", ""), errors="coerce")

days = sorted({re.search(r"(\d{6})\.csv$", f).group(1) for f in glob.glob(os.path.join(src, "high_kospi_*.csv"))})
have = set(cached_days())
tot = {"vol_n": 0, "vol_match": 0, "hi_m": 0, "hi_api": 0, "hi_both": 0}
for yymmdd in days:
    d = "20" + yymmdd
    if d not in have: print(d, "캐시 없음"); continue
    vol, highs, uppers = build_day(d)
    api_v = pd.DataFrame(vol).set_index("ticker")
    api_h = {h["ticker"] for h in highs}
    line = [d]
    for m in ("kospi", "kosdaq"):
        mv = rd(os.path.join(src, f"volume_{m}_{yymmdd}.csv"))
        mv["억"] = num(mv["거래대금"]) / 100
        j = mv.join(api_v["amount"], on="티커", how="inner")
        diff = (j["억"] - j["amount"]).abs() / j["amount"].clip(lower=0.01)
        ok = (diff <= 0.02).sum()
        tot["vol_n"] += len(j); tot["vol_match"] += ok
        top_m = list(mv.sort_values("억", ascending=False)["티커"].head(10))
        top_a = list(api_v[api_v["market"] == m.upper()].sort_values("amount", ascending=False).index[:10])
        mh = rd(os.path.join(src, f"high_{m}_{yymmdd}.csv"))
        mh = set(mh[mh["티커"].isin(api_v.index)]["티커"])  # ETF 등 Open API에 없는 종목 제외
        ah = {t for t in api_h if t in api_v.index and api_v.loc[t, "market"] == m.upper()}
        tot["hi_m"] += len(mh); tot["hi_api"] += len(ah); tot["hi_both"] += len(mh & ah)
        line.append(f"{m}: 거래대금 일치 {ok}/{len(j)}(±2%) 상위10 겹침 {len(set(top_m)&set(top_a))} | "
                    f"신고가 영웅문 {len(mh)} API {len(ah)} 공통 {len(mh & ah)}")
    line.append(f"상한가 {len(uppers)}")
    print(" / ".join(line))
print("합계", tot)
