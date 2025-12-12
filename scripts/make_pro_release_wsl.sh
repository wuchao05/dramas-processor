#!/usr/bin/env bash
# 在 WSL/Linux 下自动构建 Pro 发布包（全功能，Feishu 需 license 解锁）
#
# 发布包包含：
# - dist/drama-processor 生成的二进制
# - assets/ 资源目录（不做裁剪）
# - configs/pro.yaml（默认不包含 configs/users，避免泄露飞书密钥）
#
# 用法：
#   bash scripts/make_pro_release_wsl.sh
#   bash scripts/make_pro_release_wsl.sh --out /tmp/pro_release
#   bash scripts/make_pro_release_wsl.sh --pro-config /path/to/pro.yaml
#   bash scripts/make_pro_release_wsl.sh --skip-build
#   bash scripts/make_pro_release_wsl.sh --no-archive

set -euo pipefail

usage() {
  cat <<'EOF'
用法：bash scripts/make_pro_release_wsl.sh [选项]

选项：
  --out DIR            输出发布目录（默认：仓库根目录/pro_release）
  --pro-config PATH    要打包的配置文件（默认优先：configs/pro.yaml；会拷贝为 configs/pro.yaml）
  --skip-build         不重新编译二进制，只做打包
  --no-archive         不生成 zip/tar.gz 压缩包
  --clean              清理旧的 build/dist/spec 后再构建
  -h, --help           显示帮助

说明：
  1. 请在 WSL/Arch（或任意 Linux）里运行本脚本（输出为 Linux 二进制）。
  2. 运行前确保已安装依赖并能导入 pyinstaller：
       python -m venv .venv
       source .venv/bin/activate
       pip install -r requirements.txt
       pip install -e .
       pip install pyinstaller
  3. Pro 版本如需使用 Feishu，请先用 scripts/license_tool.py 生成密钥并签发 license.json，
     再把公钥写入 DEFAULT_PUBLIC_KEY_PEM 后重新打包。
  4. 默认不拷贝 configs/users 目录（里面可能有飞书密钥），如需带入请手动复制。
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NAME="drama-processor"
OUT_DIR="${REPO_ROOT}/pro_release"
# 默认优先使用 pro.yaml（若不存在则回退 default.yaml）
if [[ -f "${REPO_ROOT}/configs/pro.yaml" ]]; then
  PRO_CONFIG="${REPO_ROOT}/configs/pro.yaml"
else
  PRO_CONFIG="${REPO_ROOT}/configs/default.yaml"
fi

SKIP_BUILD=0
NO_ARCHIVE=0
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUT_DIR="$2"
      shift 2
      ;;
    --pro-config)
      PRO_CONFIG="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --no-archive)
      NO_ARCHIVE=1
      shift
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERR] 未知参数：$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${PRO_CONFIG}" ]]; then
  echo "[ERR] 找不到配置文件：${PRO_CONFIG}" >&2
  exit 1
fi

# 选择 python 解释器：优先使用仓库根目录的 .venv
PYTHON=""
if [[ -x "${REPO_ROOT}/.venv/bin/python3" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python3"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "[ERR] 未找到 python/python3，请先在 WSL 中安装 Python 3.8+" >&2
  exit 1
fi

if ! "${PYTHON}" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "[ERR] 未安装 pyinstaller，请先在虚拟环境中执行：pip install pyinstaller" >&2
  exit 1
fi

if [[ "${CLEAN}" -eq 1 ]]; then
  echo "[INFO] 清理旧的构建产物..."
  rm -rf "${REPO_ROOT}/build" "${REPO_ROOT}/dist" "${REPO_ROOT}/${NAME}.spec"
fi

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
  echo "[INFO] 开始构建 Pro 二进制..."
  (cd "${REPO_ROOT}" && "${PYTHON}" -m PyInstaller -F -n "${NAME}" "src/drama_processor/cli/main.py")
else
  echo "[INFO] 跳过构建，直接打包..."
fi

DIST_BIN="${REPO_ROOT}/dist/${NAME}"
if [[ ! -f "${DIST_BIN}" ]]; then
  echo "[ERR] 未找到构建产物：${DIST_BIN}" >&2
  exit 1
fi

echo "[INFO] 生成发布目录：${OUT_DIR}"
rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}/assets" "${OUT_DIR}/configs"

cp -f "${DIST_BIN}" "${OUT_DIR}/${NAME}"
chmod +x "${OUT_DIR}/${NAME}"

cp -a "${REPO_ROOT}/assets/." "${OUT_DIR}/assets/"
# Pro 包仅包含 pro.yaml（由 Pro 入口默认优先读取）
cp -f "${PRO_CONFIG}" "${OUT_DIR}/configs/pro.yaml"

echo "[OK] 发布目录已准备完成。"

if [[ "${NO_ARCHIVE}" -eq 0 ]]; then
  VERSION="$(grep -E '^version = ' "${REPO_ROOT}/pyproject.toml" | head -1 | sed -E 's/version = \"([^\"]+)\"/\\1/')"
  VERSION="${VERSION:-unknown}"
  DATE_STR="$(date +%Y%m%d)"
  ARCHIVE_BASE="${NAME}-pro-${VERSION}-${DATE_STR}-wsl"
  PARENT_DIR="$(cd "$(dirname "${OUT_DIR}")" && pwd)"
  OUT_BASENAME="$(basename "${OUT_DIR}")"

  if command -v zip >/dev/null 2>&1; then
    echo "[INFO] 打包 zip：${ARCHIVE_BASE}.zip"
    (cd "${PARENT_DIR}" && zip -qr "${ARCHIVE_BASE}.zip" "${OUT_BASENAME}")
    echo "[OK] 已生成：${PARENT_DIR}/${ARCHIVE_BASE}.zip"
  else
    echo "[INFO] 未检测到 zip，改用 tar.gz 打包"
    tar -czf "${PARENT_DIR}/${ARCHIVE_BASE}.tar.gz" -C "${PARENT_DIR}" "${OUT_BASENAME}"
    echo "[OK] 已生成：${PARENT_DIR}/${ARCHIVE_BASE}.tar.gz"
  fi
fi

echo ""
echo "下一步："
echo "1. 本地运行：./${NAME} process 或 ./${NAME} --license license.json feishu list"
echo "2. 如需发给别人，请确认 configs/pro.yaml 不含 secrets，再手动补充 license.json"
