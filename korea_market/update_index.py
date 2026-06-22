import os
import glob
from datetime import datetime

_base      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR   = os.path.join(_base, "docs")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(_base, "docs", "reports"))


def _report_items(pattern, prefix, label):
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, pattern)), reverse=True)
    if not files:
        return '<p class="none">리포트 없음</p>'
    items = ""
    for path in files:
        fname    = os.path.basename(path)
        date_str = fname.replace(prefix, "").replace(".html", "")
        date_fmt = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
        items   += f'<li><a href="reports/{fname}">📊 {date_fmt} {label}</a></li>\n'
    return f"<ul>{items}</ul>"


def update_index():
    daily     = _report_items("korea_daily_report_*.html",     "korea_daily_report_",     "일간 리포트")
    biweekly  = _report_items("korea_biweekly_report_*.html",  "korea_biweekly_report_",  "격주 리포트")
    monthly   = _report_items("korea_monthly_report_*.html",   "korea_monthly_report_",   "월간 리포트")
    quarterly = _report_items("korea_quarterly_report_*.html", "korea_quarterly_report_", "분기 리포트")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Korea Market Hub</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;
        background:#0a0a0f;color:#e8e8f0;max-width:900px;margin:0 auto;padding:40px 20px}}
  .hd-brand{{font-size:13px;font-weight:700;color:#EF4444;letter-spacing:2px;margin-bottom:6px}}
  .hd-title{{font-size:32px;font-weight:800;letter-spacing:-.5px;margin-bottom:6px}}
  .hd-sub{{font-size:13px;color:#6060a0;margin-bottom:40px}}
  .grid{{display:grid;grid-template-columns:1fr;gap:24px}}
  .section{{border-left:3px solid #3B82F6;padding-left:16px}}
  .section.biweekly{{border-color:#10B981}}
  .section.monthly{{border-color:#F59E0B}}
  .section.quarterly{{border-color:#8B5CF6}}
  .sec-title{{font-size:13px;font-weight:700;color:#9090c0;margin-bottom:12px;
              display:flex;align-items:center;gap:6px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:24px}}
  ul{{list-style:none;padding:0}}
  li{{margin-bottom:10px}}
  a{{color:#6c8cff;text-decoration:none;font-size:15px;font-weight:500}}
  a:hover{{color:#8080ff}}
  .none{{font-size:13px;color:#404060;padding:4px 0}}
  .updated{{font-size:11px;color:#303050;margin-top:48px}}
  @media(max-width:600px){{.grid2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<div class="hd-brand">KR</div>
<div class="hd-title">Korea Market <span style="color:#EF4444">Report</span></div>
<div class="hd-sub">한국 증시 분석 리포트 · 매일 장마감 후 업데이트</div>

<div class="section">
  <div class="sec-title">📊 일간 리포트</div>
  {daily}
</div>

<div class="grid2">
  <div class="section biweekly">
    <div class="sec-title">📈 격주 리포트</div>
    {biweekly}
  </div>
  <div class="section monthly">
    <div class="sec-title">📅 월간 리포트</div>
    {monthly}
  </div>
</div>

<div class="section quarterly" style="margin-top:24px">
  <div class="sec-title">🗓 분기 리포트</div>
  {quarterly}
</div>

<p class="updated">Updated: {now} KST</p>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Index] Updated")


if __name__ == "__main__":
    update_index()
