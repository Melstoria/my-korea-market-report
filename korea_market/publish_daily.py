"""일간 리포트 게시: docs/reports/*.html과 docs/index.html만 비밀값 검사 후 commit·push한다.
저장소의 다른 변경(스테이징 포함)은 건드리지 않는다(git commit --only). run_daily_auto.bat에서 PUBLISH=1일 때만 호출."""
import subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN = Path(r"C:\Users\User\Desktop\20_프로젝트\project\krx_market_bottom\trading_value\secret_scan.py")
PATHS = ["docs/reports", "docs/index.html"]

git = lambda *a: subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, encoding="utf-8")
changed = [l[3:] for l in git("status", "--porcelain", "--untracked-files=all", "--", *PATHS).stdout.splitlines()]
if not changed:
    print("변경 없음: push 생략"); sys.exit(0)
bad = [f for f in changed if not f.endswith(".html")]
if bad:
    sys.exit(f"HTML 외 파일 변경 {bad}: push 중단")
if subprocess.run([sys.executable, str(SCAN), "files", *[str(REPO / f) for f in changed]]).returncode != 0:
    sys.exit("비밀값 의심 항목 발견: push 중단")
git("add", "-f", "--", *changed)
msg = "daily report\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
c = git("commit", "--only", "-m", msg, "--", *changed)
print(c.stdout, c.stderr)
done = git("show", "--name-only", "--format=", "HEAD").stdout.split()
if not done or any(not f.startswith("docs/") or not f.endswith(".html") or ".env" in f.lower() for f in done):
    sys.exit(f"예상 밖 커밋 파일 {done}: push 중단(로컬 커밋 확인 필요)")
p = git("push", "origin", "main"); print(p.stdout, p.stderr)
sys.exit(p.returncode)
