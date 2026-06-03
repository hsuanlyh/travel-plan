#!/bin/bash
# build.sh — inline CSS/JS，用 staticrypt 加密，密碼藏在 URL hash
#
# 用法:
#   bash build.sh <密碼>                         # 產出加密檔 + 顯示 hash
#   bash build.sh <密碼> <GitHub_Pages_URL>      # 產出完整分享連結
#
# 範例:
#   bash build.sh mySecret123
#   bash build.sh mySecret123 https://yunhsuan.github.io/travel-plan/2026-kansai/

set -e

PASSWORD=${1:-""}
BASE_URL=${2:-""}

if [ -z "$PASSWORD" ]; then
  echo "❌ 請輸入密碼: bash build.sh <密碼>"
  exit 1
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
INLINE="$DIR/_inline_tmp.html"
OUT="$DIR/index.encrypted.html"

echo "📦 步驟 1：inline CSS/JS 進 HTML..."
python3 - "$DIR" <<'PYEOF'
import sys, os
d = sys.argv[1]
with open(os.path.join(d,'index.html'), 'r', encoding='utf-8') as f: html = f.read()
shared = os.path.join(d, '..', 'shared')
with open(os.path.join(shared,'style.css'), 'r', encoding='utf-8') as f: css  = f.read()
with open(os.path.join(shared,'main.js'),  'r', encoding='utf-8') as f: js   = f.read()
html = html.replace('<link rel="stylesheet" href="../shared/style.css">', f'<style>\n{css}\n</style>')
html = html.replace('<script src="../shared/main.js"></script>', f'<script>\n{js}\n</script>')
with open(os.path.join(d,'_inline_tmp.html'), 'w', encoding='utf-8') as f: f.write(html)
print("  ✅ inline 完成")
PYEOF

echo "🔒 步驟 2：staticrypt 加密（密碼藏在 URL hash）..."

# Fixed salt — keeps the URL hash identical across every rebuild.
# Same password + same salt = same hash = share link never changes.
FIXED_SALT="6b616e73616932303236657665727964"

# Step A: encrypt, write file
cd "$DIR"
mkdir -p _enc_out
staticrypt "_inline_tmp.html" \
  --password "$PASSWORD" \
  --salt "$FIXED_SALT" \
  --remember false \
  --directory "_enc_out" 2>&1

ENCRYPTED="$DIR/_enc_out/_inline_tmp.html"
if [ ! -f "$ENCRYPTED" ]; then
  echo "❌ 加密失敗：staticrypt 沒有產生輸出檔"
  echo "   請確認密碼長度 ≥ 14 字元，或檢查 staticrypt 是否正確安裝"
  rm -rf "$DIR/_enc_out" "$INLINE"
  exit 1
fi

mv "$ENCRYPTED" "$OUT"
rm -rf "$DIR/_enc_out"

# Step B: derive share hash using same fixed salt
SHARE_HASH=$(staticrypt "$OUT" \
  --password "$PASSWORD" \
  --salt "$FIXED_SALT" \
  --remember false \
  --share 2>&1 | grep "^#staticrypt_pwd=")

rm -f "$INLINE" "$DIR/.staticrypt.json"

echo ""
echo "✅ 完成！→ index.encrypted.html"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📌 上傳到 GitHub 步驟："
echo "   cp index.encrypted.html 到你的 repo，重新命名為 index.html"
echo "   （index.html / style.css / main.js 等 source 加進 .gitignore）"
echo ""

if [ -n "$BASE_URL" ]; then
  BASE_URL="${BASE_URL%/}"
  echo "🔗 分享連結（有這個連結直接開，不用輸密碼）："
  echo ""
  echo "   ${BASE_URL}/${SHARE_HASH}"
else
  echo "🔗 URL hash（貼在你的 GitHub Pages 網址後面）："
  echo ""
  echo "   ${SHARE_HASH}"
  echo ""
  echo "   例如："
  echo "   https://yourname.github.io/travel-plan/2026-kansai/${SHARE_HASH}"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
