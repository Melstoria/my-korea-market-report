"""
Korea Market HTML Report Generator v3
- KOSPI/KOSDAQ 탭 전환 시 전체 섹션 동기화
- 섹터 자금흐름, 스코어카드, 4박스, 레짐신호, 전략 모두 시장별
"""

import os, json
from datetime import datetime
from analyzer import run_analysis

OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR",
    os.path.join(os.path.dirname(__file__), "../docs/reports")
)
WEEKDAYS = ["월","화","수","목","금","토","일"]

# ETN만 제외 (전체 표시용)
ETN_KW = [" ETN", "ETN(", "ETN "]
def is_etf(name): return any(k in name for k in ETN_KW)

# 섹터 바 종목 칩 전용 — ETF·ETN 모두 제외
ETF_BRAND = [
    "KODEX","TIGER","KBSTAR","ARIRANG","ACE ","SOL ","PLUS ","KOSEF",
    "HANARO","RISE ","TIMEFOLIO","KIWOOM ","1Q ","TREX","SMART",
]
def is_etf_strict(name):
    return (any(k in name for k in ETN_KW) or
            any(name.startswith(k) or k in name for k in ETF_BRAND))

def fmt_amt(v):
    if not v: return "0억"
    if v >= 100000: return f"{v/10000:.1f}조"   # 10조 이상 → 조 단위
    if v >= 10000:  return f"{v/10000:.2f}조"   # 1조~10조 → X.XX조
    return f"{v:,.0f}억"                         # 1조 미만 → 억 단위 그대로

def fmt_pct(v):
    s = "+" if v > 0 else ""
    return f"{s}{v:.1f}%"

def cls_chg(v): return "up" if v>0 else ("dn" if v<0 else "flat")

SECTOR_COLORS = {
    "반도체/하드웨어":    "#3B82F6",
    "반도체 장비/소부장": "#6366F1",
    "빅테크/플랫폼":     "#8B5CF6",
    "자동차/부품":       "#10B981",
    "2차전지/소재":      "#F59E0B",
    "바이오/헬스케어":   "#EF4444",
    "로보틱스/자동화":   "#EC4899",
    "방산/우주":         "#F97316",
    "조선/중공업":       "#06B6D4",
    "건설/플랜트":       "#84CC16",
    "금융":              "#A78BFA",
    "에너지/유틸리티":   "#34D399",
    "통신/광통신":       "#22D3EE",
    "철강/소재":         "#9CA3AF",
    "소비재/유통":       "#FB923C",
    "기타":              "#D1D5DB",
}
SECTOR_ICONS = {
    "반도체/하드웨어":    "💠",
    "반도체 장비/소부장": "🔬",
    "빅테크/플랫폼":     "🌐",
    "자동차/부품":       "🚗",
    "2차전지/소재":      "⚡",
    "바이오/헬스케어":   "🧬",
    "로보틱스/자동화":   "🤖",
    "방산/우주":         "🚀",
    "조선/중공업":       "⚓",
    "건설/플랜트":       "🏗",
    "금융":              "🏦",
    "에너지/유틸리티":   "🔋",
    "전기전자/부품":     "🔌",
    "지주/복합기업":     "🏢",
    "통신/광통신":       "📡",
    "철강/소재":         "⚙️",
    "소비재/유통":       "🛍",
    "기타":              "📊",
}
def scolor(s): return SECTOR_COLORS.get(s, "#94A3B8")
def sicon(s):  return SECTOR_ICONS.get(s, "📊")

TAG_COLORS = {
    "반도체/하드웨어 독주": "#3B82F6",
    "주도섹터 집중":        "#6366F1",
    "강세 — 광범위 매수":   "#10B981",
    "온건 강세":            "#34D399",
    "매수 에너지 부재":     "#9CA3AF",
    "신고가 러시":          "#F59E0B",
    "신고가 확산":          "#FCD34D",
    "자동차·자동화 동반 급등": "#EC4899",
    "방산·우주 테마 이슈":  "#F97316",
    "건설일률성 급등":      "#84CC16",
    "ETF 인버스 자금 유입": "#EF4444",
    "중립":                 "#94A3B8",
}

# ── 렌더 함수 ─────────────────────────────────────────────────────────────────

def r_sector_bars(sectors, st_stocks, max_n=12):
    top = sorted([s for s in sectors if s["sector"]!="기타"],
                 key=lambda x: x["total_amount"], reverse=True)[:max_n]
    if not top: return '<p class="empty">데이터 없음</p>'
    max_amt   = max(s["total_amount"] for s in top) or 1
    total_all = sum(s["total_amount"] for s in top) or 1
    html = ""
    for s in top:
        w     = s["total_amount"] / max_amt * 100
        share = s["total_amount"] / total_all * 100
        color = scolor(s["sector"])
        stocks = st_stocks.get(s["sector"], [])
        pills = ""
        for st in stocks[:10]:
            if is_etf_strict(st.get("name","")): continue
            cc   = cls_chg(st["change_pct"])
            sign = "+" if st["change_pct"]>0 else ""
            pills += (f'<div class="st-pill">'
                      f'<span class="st-name">{st["name"]}</span>'
                      f'<span class="st-sep">|</span>'
                      f'<span class="st-amt">{fmt_amt(st["amount"])}</span>'
                      f'<span class="st-sep">·</span>'
                      f'<span class="st-pct {cc}">{sign}{st["change_pct"]:.1f}%</span>'
                      f'</div>')
        html += (f'<div class="sb-block">'
                 f'<div class="sb-hd">'
                 f'<div class="sb-left"><span class="sb-ic">{sicon(s["sector"])}</span>'
                 f'<span class="sb-nm">{s["sector"]}</span></div>'
                 f'<div class="sb-right"><span class="sb-amt">{fmt_amt(s["total_amount"])}</span>'
                 f'<span class="sb-badge">비중 {share:.1f}%</span></div>'
                 f'</div>'
                 f'<div class="sb-track"><div class="sb-fill" style="width:{w:.1f}%;background:{color}"></div></div>'
                 f'<div class="st-pills">{pills}</div>'
                 f'</div>')
    return html

def r_scorecard(sectors):
    top = sorted([s for s in sectors if s["sector"]!="기타"],
                 key=lambda x: x["total_amount"], reverse=True)[:10]
    if not top: return ""
    def char_tag(s):
        sc,hc,uc = s["sector_score"], s["high_count"], s["upper_count"]
        if sc>=70 and hc>=3: return "핵심 주도"
        if sc>=50: return "강세 지속형"
        if sc>=40: return "추세 동반"
        if hc>=2:  return "신고가 확산"
        return "관망"
    rows = ""
    for i,s in enumerate(top,1):
        w = min(100, s["sector_score"])
        c = "#3B82F6" if s["sector_score"]>=70 else ("#10B981" if s["sector_score"]>=45 else "#9CA3AF")
        rows += (f'<tr><td class="sc-rk">{i}</td>'
                 f'<td class="sc-sc">{sicon(s["sector"])} {s["sector"]}</td>'
                 f'<td class="sc-am">{fmt_amt(s["total_amount"])}</td>'
                 f'<td class="sc-br"><div class="sc-track"><div class="sc-fill" style="width:{w:.0f}%;background:{c}"></div></div>'
                 f'<span class="sc-val">{s["sector_score"]:.0f}</span></td>'
                 f'<td class="sc-sh">{s.get("share_pct",0):.1f}%</td>'
                 f'<td class="sc-ch">{char_tag(s)}</td></tr>')
    return (f'<table class="sc-table"><thead><tr>'
            f'<th>#</th><th>섹터</th><th>거래대금</th>'
            f'<th colspan="2">강도</th><th>비중</th><th>성격</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>')

SECTOR_BADGE_COLORS = {
    "반도체/하드웨어":    "#3B82F6",
    "반도체 장비/소부장": "#6366F1",
    "전기전자/부품":     "#0EA5E9",
    "빅테크/플랫폼":     "#8B5CF6",
    "자동차/부품":       "#10B981",
    "2차전지/소재":      "#F59E0B",
    "바이오/헬스케어":   "#EF4444",
    "로보틱스/자동화":   "#EC4899",
    "방산/우주":         "#F97316",
    "조선/중공업":       "#06B6D4",
    "건설/플랜트":       "#84CC16",
    "금융":              "#A78BFA",
    "에너지/유틸리티":   "#34D399",
    "지주/복합기업":     "#9CA3AF",
    "통신/광통신":       "#22D3EE",
    "철강/소재":         "#64748B",
    "소비재/유통":       "#FB923C",
}

def sector_badge(sector):
    if not sector or sector in ("기타", ""): return '<span class="bx-sec" style="background:transparent"></span>'
    color = SECTOR_BADGE_COLORS.get(sector, "#9CA3AF")
    return f'<span class="bx-sec" style="background:{color}">{sector}</span>'

def r_explosion(items, vol_top=None):
    if items:
        h = ""
        for e in items[:7]:
            if is_etf(e.get("name","")): continue
            cc = cls_chg(e.get("change_pct",0))
            h += (f'<div class="bx-row">'
                  f'<span class="bx-nm">{e["name"]}</span>{sector_badge(e.get("sector",""))}'
                  f'<div class="bx-r">'
                  f'<span class="bx-ratio">{e.get("vol_explosion_ratio",0):.0f}배</span>'
                  f'<span class="bx-pct {cc}">{fmt_pct(e.get("change_pct",0))}</span>'
                  f'</div></div>')
        return h or '<p class="empty">해당 없음</p>'
    if not vol_top:
        return '<p class="empty">전일 데이터 없음</p>'
    h = ""
    for s in vol_top[:7]:
        if is_etf(s.get("name","")): continue
        cc = cls_chg(s.get("change_pct",0))
        h += (f'<div class="bx-row">'
              f'<span class="bx-nm">{s["name"]}</span>{sector_badge(s.get("sector",""))}'
              f'<div class="bx-r">'
              f'<span class="bx-amt">{fmt_amt(s.get("amount",0))}</span>'
              f'<span class="bx-pct {cc}">{fmt_pct(s.get("change_pct",0))}</span>'
              f'</div></div>')
    return h or '<p class="empty">해당 없음</p>'

def r_gainers(items):
    if not items: return '<p class="empty">해당 없음</p>'
    h = ""
    for s in items[:7]:
        if is_etf(s.get("name","")): continue
        cc = cls_chg(s.get("change_pct",0))
        h += (f'<div class="bx-row">'
              f'<span class="bx-nm">{s["name"]}</span>{sector_badge(s.get("sector",""))}'
              f'<span class="bx-pct {cc}">{fmt_pct(s.get("change_pct",0))}</span>'
              f'</div>')
    return h or '<p class="empty">해당 없음</p>'

def r_voltop(items):
    if not items: return '<p class="empty">해당 없음</p>'
    h = ""
    for s in items[:7]:
        if is_etf(s.get("name","")): continue
        cc = cls_chg(s.get("change_pct",0))
        h += (f'<div class="bx-row">'
              f'<span class="bx-nm">{s["name"]}</span>{sector_badge(s.get("sector",""))}'
              f'<div class="bx-r"><span class="bx-amt">{fmt_amt(s.get("amount",0))}</span>'
              f'<span class="bx-pct {cc}">{fmt_pct(s.get("change_pct",0))}</span></div>'
              f'</div>')
    return h or '<p class="empty">해당 없음</p>'

def r_highvol(items):
    if not items: return '<p class="empty">해당 없음</p>'
    h = ""
    for s in items[:7]:
        if is_etf(s.get("name","")): continue
        cc = cls_chg(s.get("change_pct",0))
        vr = s.get("vol_ratio") or 1
        h += (f'<div class="bx-row">'
              f'<span class="bx-nm">{s["name"]}</span>{sector_badge(s.get("sector",""))}'
              f'<div class="bx-r"><span class="bx-pct {cc}">{fmt_pct(s.get("change_pct",0))}</span>'
              f'<span class="bx-vol">×{vr:.1f}</span></div>'
              f'</div>')
    return h or '<p class="empty">해당 없음</p>'

def r_high_list(stocks):
    """신고가 종목 전체 — 섹터별 그룹으로 표시"""
    if not stocks:
        return '<p class="empty">신고가 종목 없음</p>'

    # 섹터별 그룹핑
    from collections import defaultdict
    by_sector = defaultdict(list)
    for s in stocks:
        sec = s.get("sector","") or "기타"
        by_sector[sec].append(s)

    # 섹터별 거래대금 합산 후 내림차순
    sector_order = sorted(
        [sec for sec in by_sector if sec != "기타"],
        key=lambda x: sum(s.get("amount",0) for s in by_sector[x]),
        reverse=True
    )
    if "기타" in by_sector:
        sector_order.append("기타")

    h = '<div class="hl-grid">'
    for sec in sector_order:
        items = by_sector[sec]
        color = SECTOR_BADGE_COLORS.get(sec, "#9CA3AF")
        chips = ""
        for st in sorted(items, key=lambda x: x.get("change_pct",0), reverse=True):
            cc  = cls_chg(st.get("change_pct",0))
            sign = "+" if st.get("change_pct",0) > 0 else ""
            chips += (f'<span class="hl-chip">'
                      f'<span class="hl-nm">{st["name"]}</span>'
                      f'<span class="hl-pct {cc}">{sign}{st.get("change_pct",0):.1f}%</span>'
                      f'</span>')
        h += (f'<div class="hl-sec">'
              f'<div class="hl-sec-hd" style="border-left:3px solid {color}">'
              f'<span class="hl-sec-nm">{sicon(sec)} {sec}</span>'
              f'<span class="hl-sec-cnt">{len(items)}개</span>'
              f'</div>'
              f'<div class="hl-chips">{chips}</div>'
              f'</div>')
    h += '</div>'
    return h

def r_regime(regime):
    tags = regime.get("tags", [])
    tag_html = ""
    for t in tags:
        c = TAG_COLORS.get(t, "#94A3B8")
        tag_html += (f'<span class="rg-tag" style="background:{c}20;'
                     f'color:{c};border:1px solid {c}50">{t}</span>')
    txt = regime.get("explanation","")
    return f'<div class="rg-tags">{tag_html}</div><div class="rg-txt">{txt}</div>'

def r_strategy(strat):
    items = [
        ("단기", "1~5일",   strat.get("short",{}), "#3B82F6"),
        ("중기", "1~3개월", strat.get("mid",{}),   "#10B981"),
        ("장기", "6개월+",  strat.get("long",{}),  "#F59E0B"),
    ]
    h = '<div class="strat-grid">'
    for label, period, s, color in items:
        stocks = s.get("stocks", [])
        chips  = "".join(f'<span class="st-chip">{n}</span>' for n in stocks if n)
        pts    = "".join(f'<li>{p}</li>' for p in s.get("points",[]))
        h += (f'<div class="strat-card" style="border-top:3px solid {color}">'
              f'<div class="strat-hd">'
              f'<span class="strat-lbl" style="color:{color}">{label}</span>'
              f'<span class="strat-period">{period}</span>'
              f'<span class="strat-stance">{s.get("stance","")}</span>'
              f'</div>'
              f'{f"<div class=\"strat-chips\">{chips}</div>" if chips else ""}'
              f'<ul class="strat-pts">{pts}</ul>'
              f'</div>')
    h += '</div>'
    return h

def r_rotation(rotation):
    sig = rotation.get("signal","—")
    det = rotation.get("detail","")
    return (f'<div class="rot-box">'
            f'<div class="rot-sig">{sig}</div>'
            f'<div class="rot-det">{det}</div>'
            f'</div>')

# ── 메인 생성 ─────────────────────────────────────────────────────────────────

def generate_report(data: dict, output_dir: str = None) -> str:
    if not data: raise ValueError("No data")
    out = output_dir or OUTPUT_DIR
    os.makedirs(out, exist_ok=True)

    date_str = data["date"]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_kor = date_obj.strftime("%Y.%m.%d")
    weekday  = WEEKDAYS[date_obj.weekday()]

    # 시장별 데이터
    def g(k, fallback=None): return data.get(k, fallback if fallback is not None else [])

    kospi_total  = g("kospi_total",  0)
    kosdaq_total = g("kosdaq_total", 0)

    # 헤더 KPI — 탭 공통(전체) + 탭별
    # KOSPI 헤더
    gk = g("gainers_kospi")
    gd = g("gainers_kosdaq")
    top_gainer_kospi  = gk[0] if gk else {}
    top_gainer_kosdaq = gd[0] if gd else {}

    ek = g("explosion_kospi")
    ed = g("explosion_kosdaq")
    expl_kospi  = ek[0] if ek else {}
    expl_kosdaq = ed[0] if ed else {}

    # 섹터 바
    bars_kp = r_sector_bars(g("sectors_kospi"),  g("sector_stocks_kospi",{}))
    bars_kd = r_sector_bars(g("sectors_kosdaq"), g("sector_stocks_kosdaq",{}))

    # 스코어카드
    sc_kp = r_scorecard(g("sectors_kospi"))
    sc_kd = r_scorecard(g("sectors_kosdaq"))

    # 4박스
    expl_kp_h  = r_explosion(g("explosion_kospi"),  g("vol_top5_kospi"))
    expl_kd_h  = r_explosion(g("explosion_kosdaq"), g("vol_top5_kosdaq"))
    gain_kp_h  = r_gainers(g("gainers_kospi"))
    gain_kd_h  = r_gainers(g("gainers_kosdaq"))
    volt_kp_h  = r_voltop(g("vol_top5_kospi"))
    volt_kd_h  = r_voltop(g("vol_top5_kosdaq"))
    hvol_kp_h  = r_highvol(g("high_vol_kospi"))
    hvol_kd_h  = r_highvol(g("high_vol_kosdaq"))

    # 신고가 목록
    hl_kp_h = r_high_list(g("high_stocks_kospi"))
    hl_kd_h = r_high_list(g("high_stocks_kosdaq"))

    # 레짐
    reg_kp_h = r_regime(g("regime_kospi",{}))
    reg_kd_h = r_regime(g("regime_kosdaq",{}))

    # 전략
    strat_kp_h = r_strategy(g("strategy_kospi",{}))
    strat_kd_h = r_strategy(g("strategy_kosdaq",{}))

    # 순환매 (공통)
    rot_h = r_rotation(g("rotation",{}))

    def kpi_val(s, key, fmt="pct"):
        v = s.get(key, 0) or 0
        if fmt == "pct": return fmt_pct(v)
        if fmt == "amt": return fmt_amt(v)
        return str(v)

    gkn = top_gainer_kospi.get("name","—")
    gkv = fmt_pct(top_gainer_kospi.get("change_pct",0)) if top_gainer_kospi else "—"
    gdn = top_gainer_kosdaq.get("name","—")
    gdv = fmt_pct(top_gainer_kosdaq.get("change_pct",0)) if top_gainer_kosdaq else "—"
    ekn = expl_kospi.get("name","—")
    ekv = f"{expl_kospi.get('vol_explosion_ratio',0):.0f}%" if expl_kospi else "—"
    edn = expl_kosdaq.get("name","—")
    edv = f"{expl_kosdaq.get('vol_explosion_ratio',0):.0f}%" if expl_kosdaq else "—"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{date_kor} 국내 시장 일일 분석</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Pretendard',sans-serif;background:#fff;color:#1C1C1E;font-size:13px;line-height:1.5}}
.page{{max-width:900px;margin:0 auto;padding:24px 20px 80px}}

/* Header */
.hd-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}}
.hd-title{{font-size:22px;font-weight:700;letter-spacing:-.5px}}
.hd-sub{{font-size:11px;color:#8E8E93;margin-top:3px}}
.mkt-tabs{{display:flex;gap:6px}}
.mkt-tab{{padding:6px 18px;border-radius:20px;font-size:11px;font-weight:700;
           border:1.5px solid #D1D5DB;color:#6B7280;cursor:pointer;transition:.15s;background:#fff}}
.mkt-tab.active{{background:#1C1C1E;color:#fff;border-color:#1C1C1E}}

/* KPI */
.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:28px}}
.kpi{{background:#F9FAFB;border-radius:12px;padding:14px 16px}}
.kpi-lbl{{font-size:10px;color:#8E8E93;font-weight:500;margin-bottom:5px}}
.kpi-val{{font-size:22px;font-weight:700;letter-spacing:-.5px}}
.kpi-val.blue{{color:#3B82F6}}
.kpi-val.red{{color:#EF4444}}
.kpi-sub{{font-size:10px;color:#8E8E93;margin-top:3px}}

/* Section */
.sec{{margin-top:26px}}
.sec-title{{font-size:13px;font-weight:700;color:#1C1C1E;margin-bottom:12px;
            padding-left:10px;border-left:3px solid #3B82F6}}

/* Tab content */
.tab{{display:none}}.tab.active{{display:block}}

/* Sector bar */
.sb-block{{margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #F3F4F6}}
.sb-block:last-child{{border-bottom:none;margin-bottom:0}}
.sb-hd{{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}}
.sb-left{{display:flex;align-items:center;gap:6px}}
.sb-ic{{font-size:14px}}
.sb-nm{{font-size:12.5px;font-weight:700;color:#1C1C1E}}
.sb-right{{display:flex;align-items:center;gap:7px}}
.sb-amt{{font-size:13px;font-weight:700;color:#1C1C1E}}
.sb-badge{{font-size:10px;font-weight:600;color:#6B7280;background:#F3F4F6;padding:2px 8px;border-radius:20px}}
.sb-track{{background:#F3F4F6;border-radius:4px;height:6px;overflow:hidden;margin-bottom:8px}}
.sb-fill{{height:100%;border-radius:4px}}
.st-pills{{display:flex;flex-wrap:wrap;gap:4px}}
.st-pill{{display:inline-flex;align-items:center;gap:4px;background:#fff;
          border:1px solid #E5E7EB;border-radius:8px;padding:3px 9px}}
.st-name{{font-size:11px;font-weight:500;color:#374151}}
.st-sep{{font-size:10px;color:#D1D5DB}}
.st-amt{{font-size:10px;color:#9CA3AF}}
.st-pct{{font-size:10.5px;font-weight:700}}

/* Scorecard */
.sc-table{{width:100%;border-collapse:collapse;font-size:11.5px}}
.sc-table thead th{{background:#F9FAFB;color:#6B7280;font-size:10px;font-weight:600;
                    padding:7px 10px;text-align:left;border-bottom:1px solid #E5E7EB}}
.sc-table tbody tr:hover{{background:#FAFAFA}}
.sc-table td{{padding:8px 10px;border-bottom:1px solid #F3F4F6;vertical-align:middle}}
.sc-rk{{font-weight:700;color:#3B82F6;width:24px}}
.sc-sc{{font-weight:600;white-space:nowrap}}
.sc-am{{color:#374151;font-variant-numeric:tabular-nums}}
.sc-br{{display:flex;align-items:center;gap:6px;min-width:110px}}
.sc-track{{flex:1;background:#F3F4F6;border-radius:3px;height:5px;overflow:hidden}}
.sc-fill{{height:100%;border-radius:3px}}
.sc-val{{font-size:10px;color:#6B7280;width:22px;text-align:right}}
.sc-sh{{color:#9CA3AF;font-size:10.5px}}
.sc-ch{{color:#6B7280;font-size:10.5px}}

/* 4 boxes */
.box-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.bx{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:14px 16px}}
.bx-hd{{font-size:11px;font-weight:700;color:#374151;margin-bottom:10px;display:flex;align-items:center;gap:5px}}
.bx-row{{display:grid;grid-template-columns:1fr auto auto;align-items:center;
          padding:6px 0;border-bottom:1px solid #F9FAFB;gap:0}}
.bx-row:last-child{{border-bottom:none}}
.bx-nm{{font-size:11.5px;font-weight:500;color:#1C1C1E;padding-right:8px;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bx-r{{display:flex;align-items:center;gap:6px}}
.bx-ratio{{font-size:12px;font-weight:700;color:#EF4444}}
.bx-amt{{font-size:12px;font-weight:700;color:#1C1C1E}}
.bx-pct{{font-size:12px;font-weight:700}}
.bx-vol{{font-size:10px;color:#9CA3AF}}
  .bx-sec{{font-size:9px;font-weight:700;color:#fff;padding:2px 7px;
           border-radius:4px;white-space:nowrap;letter-spacing:.2px;
           margin-right:8px;display:inline-block}}

  /* High list */
  .hl-grid{{display:flex;flex-direction:column;gap:12px}}
  .hl-sec{{background:#FAFAFA;border-radius:10px;padding:10px 12px}}
  .hl-sec-hd{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding-left:8px}}
  .hl-sec-nm{{font-size:12px;font-weight:700;color:#1C1C1E}}
  .hl-sec-cnt{{font-size:10px;color:#9CA3AF}}
  .hl-chips{{display:flex;flex-wrap:wrap;gap:5px}}
  .hl-chip{{display:inline-flex;align-items:center;gap:4px;background:#fff;border:1px solid #E5E7EB;border-radius:6px;padding:3px 8px}}
  .hl-nm{{font-size:11px;font-weight:500;color:#374151}}
  .hl-pct{{font-size:10.5px;font-weight:700}}
  /* Regime */
.rg-tags{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}}
.rg-tag{{font-size:11px;font-weight:600;padding:4px 11px;border-radius:20px}}
.rg-txt{{font-size:12px;color:#374151;line-height:1.7;background:#F9FAFB;padding:12px 14px;border-radius:10px}}

/* Strategy */
.strat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.strat-card{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:14px 16px}}
.strat-hd{{display:flex;flex-direction:column;gap:1px;margin-bottom:10px}}
.strat-lbl{{font-size:13px;font-weight:700}}
.strat-period{{font-size:10px;color:#9CA3AF}}
.strat-stance{{font-size:10.5px;color:#6B7280;margin-top:2px}}
.strat-chips{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}}
.st-chip{{font-size:10px;background:#F3F4F6;padding:3px 8px;border-radius:20px;color:#374151}}
.strat-pts{{padding-left:14px}}
.strat-pts li{{font-size:11px;color:#6B7280;margin-bottom:4px;line-height:1.55}}

/* Rotation */
.rot-box{{background:#F9FAFB;border-radius:10px;padding:12px 16px}}
.rot-sig{{font-size:13px;font-weight:600;color:#1C1C1E}}
.rot-det{{font-size:11px;color:#6B7280;margin-top:4px}}

/* Color utils */
.up{{color:#EF4444}}.dn{{color:#3B82F6}}.flat{{color:#9CA3AF}}
.empty{{font-size:11px;color:#9CA3AF;padding:8px 0}}

@media(max-width:640px){{
  .kpi-row{{grid-template-columns:1fr 1fr}}
  .box-grid{{grid-template-columns:1fr}}
  .strat-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<div class="page">

<div class="hd-top">
  <div>
    <div class="hd-title">{date_kor} 국내 시장 일일 분석</div>
    <div class="hd-sub">KOSPI · KOSDAQ 거래대금 상위 기준 &nbsp;·&nbsp; {weekday}요일</div>
  </div>
  <div class="mkt-tabs">
    <button class="mkt-tab active" onclick="sw('kospi',this)">KOSPI</button>
    <button class="mkt-tab"       onclick="sw('kosdaq',this)">KOSDAQ</button>
  </div>
</div>

<!-- KPI -->
<div class="kpi-row">
  <div class="kpi">
    <div class="kpi-lbl" id="kpi-total-lbl">KOSPI 총 거래대금</div>
    <div class="kpi-val blue" id="kpi-total">{fmt_amt(kospi_total)}</div>
    <div class="kpi-sub">상위 기준</div>
  </div>
  <div class="kpi">
    <div class="kpi-lbl" id="kpi-expl-lbl">거래 폭발 최고</div>
    <div class="kpi-val red" id="kpi-expl">{ekv}</div>
    <div class="kpi-sub" id="kpi-expl-nm">{ekn}</div>
  </div>
  <div class="kpi">
    <div class="kpi-lbl" id="kpi-gain-lbl">최고 상승 종목</div>
    <div class="kpi-val red" id="kpi-gain">{gkv}</div>
    <div class="kpi-sub" id="kpi-gain-nm">{gkn}</div>
  </div>
  <div class="kpi">
    <div class="kpi-lbl" id="kpi-high-lbl">신고가 (KOSPI)</div>
    <div class="kpi-val blue" id="kpi-high">{data.get("high_kospi",  data.get("high_total",0))}개</div>
    <div class="kpi-sub">비ETN 기준</div>
  </div>
</div>

<!-- 섹터 자금흐름 -->
<div class="sec">
  <div class="sec-title" id="sec-flow-title">섹터 자금흐름 — KOSPI</div>
  <div id="tab-flow-kospi"  class="tab active">{bars_kp}</div>
  <div id="tab-flow-kosdaq" class="tab">{bars_kd}</div>
</div>

<!-- 섹터 강도 스코어카드 -->
<div class="sec">
  <div class="sec-title" id="sec-sc-title">섹터 강도 스코어카드 — KOSPI</div>
  <div id="tab-sc-kospi"  class="tab active">{sc_kp}</div>
  <div id="tab-sc-kosdaq" class="tab">{sc_kd}</div>
</div>

<!-- 4 박스 -->
<div class="sec">
  <div class="box-grid">
    <div class="bx">
      <div class="bx-hd">💥 거래대금 {"폭발 (전일비)" if data.get("prev_date") else "TOP (전일비 집계 전)"}</div>
      <div id="tab-expl-kospi"  class="tab active">{expl_kp_h}</div>
      <div id="tab-expl-kosdaq" class="tab">{expl_kd_h}</div>
    </div>
    <div class="bx">
      <div class="bx-hd">📈 주가 상승률 상위</div>
      <div id="tab-gain-kospi"  class="tab active">{gain_kp_h}</div>
      <div id="tab-gain-kosdaq" class="tab">{gain_kd_h}</div>
    </div>
    <div class="bx">
      <div class="bx-hd">💰 거래대금 절대액 TOP5</div>
      <div id="tab-volt-kospi"  class="tab active">{volt_kp_h}</div>
      <div id="tab-volt-kosdaq" class="tab">{volt_kd_h}</div>
    </div>
    <div class="bx">
      <div class="bx-hd">🎯 고점수 + 대량거래</div>
      <div id="tab-hvol-kospi"  class="tab active">{hvol_kp_h}</div>
      <div id="tab-hvol-kosdaq" class="tab">{hvol_kd_h}</div>
    </div>
  </div>
</div>

<!-- 신고가 종목 -->
<div class="sec">
  <div class="sec-title" id="sec-hl-title">신고가 종목 — KOSPI</div>
  <div id="tab-hl-kospi"  class="tab active">{hl_kp_h}</div>
  <div id="tab-hl-kosdaq" class="tab">{hl_kd_h}</div>
</div>

<!-- 시장 레짐 신호 -->
<div class="sec">
  <div class="sec-title" id="sec-rg-title">시장 레짐 신호 — KOSPI</div>
  <div id="tab-rg-kospi"  class="tab active">{reg_kp_h}</div>
  <div id="tab-rg-kosdaq" class="tab">{reg_kd_h}</div>
</div>

<!-- 순환매 (공통) -->
<div class="sec">
  {rot_h}
</div>

<!-- 시간 지평별 전략 -->
<div class="sec">
  <div class="sec-title" id="sec-st-title">시간 지평별 전략 — KOSPI</div>
  <div id="tab-st-kospi"  class="tab active">{strat_kp_h}</div>
  <div id="tab-st-kosdaq" class="tab">{strat_kd_h}</div>
</div>

</div>
<script>
var KPI = {{
  kospi:  {{ total:'{fmt_amt(kospi_total)}',  expl:'{ekv}',  explNm:'{ekn}',  gain:'{gkv}',  gainNm:'{gkn}',  high:'{data.get("high_kospi", data.get("high_total",0))}개'  }},
  kosdaq: {{ total:'{fmt_amt(kosdaq_total)}', expl:'{edv}',  explNm:'{edn}',  gain:'{gdv}',  gainNm:'{gdn}',  high:'{data.get("high_kosdaq", data.get("high_total",0))}개'  }}
}};
var TABS = ['flow','sc','expl','gain','volt','hvol','hl','rg','st'];
var SEC_LABELS = {{
  'flow': '섹터 자금흐름',
  'sc':   '섹터 강도 스코어카드',
  'hl':   '신고가 종목',
  'rg':   '시장 레짐 신호',
  'st':   '시간 지평별 전략'
}};
function sw(mkt, btn) {{
  document.querySelectorAll('.mkt-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  TABS.forEach(function(t) {{
    var kp = document.getElementById('tab-'+t+'-kospi');
    var kd = document.getElementById('tab-'+t+'-kosdaq');
    if (!kp || !kd) return;
    if (mkt==='kospi')  {{ kp.classList.add('active'); kd.classList.remove('active'); }}
    else                {{ kd.classList.add('active'); kp.classList.remove('active'); }}
  }});
  var label = mkt==='kospi' ? 'KOSPI' : 'KOSDAQ';
  Object.keys(SEC_LABELS).forEach(function(k) {{
    var el = document.getElementById('sec-'+k+'-title');
    if (el) el.textContent = SEC_LABELS[k] + ' — ' + label;
  }});
  var k = KPI[mkt];
  document.getElementById('kpi-total-lbl').textContent = label+' 총 거래대금';
  document.getElementById('kpi-total').textContent = k.total;
  document.getElementById('kpi-expl').textContent  = k.expl;
  document.getElementById('kpi-expl-nm').textContent = k.explNm;
  document.getElementById('kpi-gain').textContent  = k.gain;
  document.getElementById('kpi-gain-nm').textContent = k.gainNm;
  document.getElementById('kpi-high').textContent = k.high;
  document.getElementById('kpi-high-lbl').textContent = '신고가 (' + label + ')';
}}
</script>
</body>
</html>"""

    filename = f"korea_daily_report_{date_str.replace('-','')}.html"
    filepath = os.path.join(out, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Report] 저장: {filepath}")
    return filepath

if __name__ == "__main__":
    data = run_analysis()
    if data:
        generate_report(data)
