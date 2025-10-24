#!/opt/homebrew/bin/bash
# 保留白名单中的顶层目录（每个剧=一个顶层目录），其余清理/移动
# 用法：
#   pbpaste | ./keep-shows-v2.sh "/Volumes/SSD1T/dramas"           # 预演（不删除）
#   pbpaste | ./keep-shows-v2.sh --apply "/Volumes/SSD1T/dramas"   # 真删/真移动
#   可选： --to "/Volumes/HDD4T/_Recycle"   # 不直接删，先移到回收目录
#         --case-insensitive                # 名称忽略大小写
set -euo pipefail
IFS=$'\n\t'
LC_ALL=C

APPLY=0
MOVE_TO=""
CASE_INS=0
SRC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --to) MOVE_TO="${2:-}"; shift 2 ;;
    --case-insensitive) CASE_INS=1; shift ;;
    -*)
      echo "[ERR] 未知参数：$1" >&2; exit 2 ;;
    *)
      SRC="$1"; shift ;;
  esac
done

if [[ -z "${SRC}" ]]; then
  echo "[ERR] 请输入源目录，例如：/Volumes/SSD1T/dramas" >&2; exit 2
fi
if [[ ! -d "${SRC}" ]]; then
  echo "[ERR] 源目录不存在：${SRC}" >&2; exit 2
fi
if [[ -n "${MOVE_TO}" ]]; then
  mkdir -p "${MOVE_TO}" || { echo "[ERR] 无法创建移动目标目录：${MOVE_TO}" >&2; exit 2; }
fi

WL_FILE="$(mktemp)"; trap 'rm -f "$WL_FILE" "$WL_AVAIL" "$WL_MISS"' EXIT

# 读取白名单（来自 STDIN 或剪贴板），规范化、去重
read_whitelist() {
  sed -E 's/\r$//' \
  | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' \
  | awk 'NF>0' \
  | ( [[ $CASE_INS -eq 1 ]] && awk '{print tolower($0)}' || cat ) \
  | sort -u > "$WL_FILE"
}

if [ -t 0 ]; then
  command -v pbpaste >/dev/null 2>&1 || { echo "[ERR] 没有 STDIN 或 pbpaste" >&2; exit 2; }
  pbpaste | read_whitelist
else
  read_whitelist
fi
[[ -s "$WL_FILE" ]] || { echo "[ERR] 白名单为空" >&2; exit 2; }

echo "======= 白名单（共 $(wc -l < "$WL_FILE" | tr -d ' ') 条）示例 ======="
head -n 10 "$WL_FILE"; [[ $(wc -l < "$WL_FILE") -gt 10 ]] && echo "(仅展示前 10 条...)"
echo "============================================="

# 列出源目录下的顶层目录名清单（只取 basename）
echo "[INFO] 正在扫描顶层目录：${SRC} ..."
mapfile -d '' DIR_PATHS < <(find "$SRC" -mindepth 1 -maxdepth 1 -type d -print0)

TOTAL=${#DIR_PATHS[@]}
echo "[INFO] 顶层目录数量：$TOTAL"

# 构造“可用目录名”列表（可选大小写折叠）
AVAIL_FILE="$(mktemp)"; WL_MISS="$(mktemp)"
: > "$AVAIL_FILE"
for p in "${DIR_PATHS[@]}"; do
  name="$(basename "$p")"
  if [[ $CASE_INS -eq 1 ]]; then name="$(printf "%s" "$name" | tr '[:upper:]' '[:lower:]')"; fi
  printf "%s\n" "$name" >> "$AVAIL_FILE"
done
sort -u -o "$AVAIL_FILE" "$AVAIL_FILE"

# 计算【白名单中但盘上不存在】的剧
comm -23 <(sort -u "$WL_FILE") <(sort -u "$AVAIL_FILE") > "$WL_MISS" || true
MISS_CNT=$(wc -l < "$WL_MISS" | tr -d ' ')
if [[ "$MISS_CNT" -gt 0 ]]; then
  echo ""
  echo "⚠️  以下白名单剧目在磁盘中【未找到】（共 ${MISS_CNT} 条，展示前 20 条）："
  head -n 20 "$WL_MISS"
  [[ "$MISS_CNT" -gt 20 ]] && echo "(其余 $(($MISS_CNT-20)) 条已省略)"
fi

# 根据白名单判定保留/清理
declare -a TO_KEEP=() TO_DELETE=()
# 构建白名单为 grep -F -x 快速匹配
while IFS= read -r -d '' item; do
  base="$(basename "$item")"
  key="$base"
  if [[ $CASE_INS -eq 1 ]]; then
    key="$(printf "%s" "$key" | tr '[:upper:]' '[:lower:]')"
  fi
  if grep -Fxq -- "$key" "$WL_FILE"; then
    TO_KEEP+=("$item")
  else
    TO_DELETE+=("$item")
  fi
done < <(printf '%s\0' "${DIR_PATHS[@]}")

echo ""
echo "[SUMMARY] 将保留目录数：${#TO_KEEP[@]}"
echo "[SUMMARY] 将清理目录数：${#TO_DELETE[@]}"

if [[ $APPLY -eq 0 ]]; then
  echo ""
  echo "【Dry-run 预演】以下目录将被清理（不执行删除/移动）："
  for p in "${TO_DELETE[@]}"; do echo "  - $p"; done
  echo ""
  echo "要真正执行，请加： --apply"
  [[ -n "${MOVE_TO}" ]] && echo "当前设置为移动到：${MOVE_TO}"
  exit 0
fi

echo ""
echo "【执行中】开始处理未在白名单中的目录..."
for p in "${TO_DELETE[@]}"; do
  if [[ -n "${MOVE_TO}" ]]; then
    ts="$(date +%Y%m%d-%H%M%S)"
    dest="${MOVE_TO}/$(basename "$p")__${ts}"
    echo "  移动：$p -> $dest"
    mv -- "$p" "$dest"
  else
    echo "  删除：$p"
    rm -rf -- "$p"
  fi
done
echo "完成 ✅"
