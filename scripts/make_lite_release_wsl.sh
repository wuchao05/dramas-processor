#!/usr/bin/env bash
# 在 WSL/Linux 下自动构建 Lite 发布包（无 Feishu）
#
# 发布包包含：
# - dist/drama-processor-lite 生成的二进制
# - assets/ 资源目录
# - configs/lite.yaml（请在打包前把用户配置写进去）
#
# 用法：
#   bash scripts/make_lite_release_wsl.sh
#   bash scripts/make_lite_release_wsl.sh --out /tmp/lite_release
#   bash scripts/make_lite_release_wsl.sh --lite-config /path/to/lite.yaml
#   bash scripts/make_lite_release_wsl.sh --skip-build   # 仅打包，不重新编译
#   bash scripts/make_lite_release_wsl.sh --no-archive   # 不生成压缩包

set -euo pipefail

usage() {
  cat <<'EOF'
用法：bash scripts/make_lite_release_wsl.sh [选项]

选项：
  --out DIR           输出发布目录（默认：仓库根目录/lite_release）
  --lite-config PATH  要打包的 lite 配置文件（默认：configs/lite.yaml）
  --skip-build        不重新编译二进制，只做打包
  --no-archive        不生成 zip/tar.gz 压缩包
  --clean             清理旧的 build/dist/spec 后再构建
  -h, --help          显示帮助

说明：
  1. 请在 WSL/Arch Linux（或任意 Linux）里运行本脚本（输出为 Linux 二进制）。
  2. 运行前确保已安装依赖并能导入 pyinstaller：
       pip install -r requirements.txt
       pip install -e .
       pip install pyinstaller
  3. lite.yaml 需要提前写入你朋友的用户配置（默认目录/文案/色板等）。
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NAME="drama-processor-lite"
OUT_DIR="${REPO_ROOT}/lite_release"
LITE_CONFIG="${REPO_ROOT}/configs/lite.yaml"

SKIP_BUILD=0
NO_ARCHIVE=0
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUT_DIR="$2"
      shift 2
      ;;
    --lite-config)
      LITE_CONFIG="$2"
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

if [[ ! -f "${LITE_CONFIG}" ]]; then
  echo "[ERR] 找不到 lite 配置文件：${LITE_CONFIG}" >&2
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
  echo "[ERR] 未安装 pyinstaller。" >&2
  echo "" >&2
  echo "在 Arch/WSL 里系统 Python 通常启用 PEP 668，系统 pip 不能直接装包。" >&2
  echo "推荐做法：在仓库根目录创建并激活虚拟环境后安装：" >&2
  echo "  python -m venv .venv" >&2
  echo "  source .venv/bin/activate" >&2
  echo "  pip install -r requirements.txt" >&2
  echo "  pip install -e ." >&2
  echo "  pip install pyinstaller" >&2
  echo "" >&2
  echo "或者用 pacman 安装（包名可先 pacman -Ss pyinstaller 查询）。" >&2
  exit 1
fi

if [[ "${CLEAN}" -eq 1 ]]; then
  echo "[INFO] 清理旧的构建产物..."
  rm -rf "${REPO_ROOT}/build" "${REPO_ROOT}/dist" "${REPO_ROOT}/${NAME}.spec"
fi

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
  echo "[INFO] 开始构建 Lite 二进制..."
  # PyInstaller 需要传入入口脚本路径（不能用 python 的 -m 模块方式）
  (cd "${REPO_ROOT}" && "${PYTHON}" -m PyInstaller -F -n "${NAME}" "src/drama_processor/cli/lite_main.py")
else
  echo "[INFO] 跳过构建，直接打包..."
fi

DIST_BIN="${REPO_ROOT}/dist/${NAME}"
if [[ ! -f "${DIST_BIN}" ]]; then
  echo "[ERR] 未找到构建产物：${DIST_BIN}" >&2
  echo "请确认 PyInstaller 是否成功执行。" >&2
  exit 1
fi

echo "[INFO] 生成发布目录：${OUT_DIR}"
rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}/assets" "${OUT_DIR}/configs"

cp -f "${DIST_BIN}" "${OUT_DIR}/${NAME}"
chmod +x "${OUT_DIR}/${NAME}"

cp -a "${REPO_ROOT}/assets/." "${OUT_DIR}/assets/"
cp -f "${LITE_CONFIG}" "${OUT_DIR}/configs/lite.yaml"

echo "[OK] 发布目录已准备完成。"

if [[ "${NO_ARCHIVE}" -eq 0 ]]; then
  VERSION="$(grep -E '^version = ' "${REPO_ROOT}/pyproject.toml" | head -1 | sed -E 's/version = "([^"]+)"/\1/')"
  VERSION="${VERSION:-unknown}"
  DATE_STR="$(date +%Y%m%d)"
  ARCHIVE_BASE="${NAME}-${VERSION}-${DATE_STR}-wsl"
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
else
  echo "[INFO] 已按要求跳过压缩包生成。"
fi

echo ""
echo "下一步（发给朋友）："
echo "1. 把生成的压缩包或 ${OUT_DIR} 整个目录发给他"
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  case "${ID:-}" in
    arch|manjaro|endeavouros)
      echo "2. 让他在 WSL/Arch 中安装 ffmpeg：sudo pacman -S ffmpeg"
      ;;
    ubuntu|debian)
      echo "2. 让他在 WSL/Ubuntu 中安装 ffmpeg：sudo apt-get install ffmpeg"
      ;;
    fedora|centos|rhel)
      echo "2. 让他在 WSL/Fedora/CentOS 中安装 ffmpeg：sudo dnf install ffmpeg 或 sudo yum install ffmpeg"
      ;;
    *)
      echo "2. 让他在 WSL 中安装 ffmpeg（按发行版选择包管理器）"
      ;;
  esac
else
  echo "2. 让他在 WSL 中安装 ffmpeg（按发行版选择包管理器）"
fi
echo "3. 解压后执行：./${NAME} -c configs/lite.yaml process /mnt/d/短剧素材目录"
