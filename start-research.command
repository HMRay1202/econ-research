#!/bin/zsh

set -euo pipefail
setopt no_bg_nice

PROJECT_DIR="${0:A:h}"
APP_URL="http://127.0.0.1:8000/"
HEALTH_URL="${APP_URL}health"
UI_VERSION="2026-08-27-formula-v2"
UI_VERSION_URL="${APP_URL}api/ui-version"

cd "$PROJECT_DIR"

find_conda() {
  if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE}" ]]; then
    print -r -- "$CONDA_EXE"
    return
  fi

  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return
  fi

  local user_directory="${HOME:?Home directory is unavailable}"
  local candidate
  for candidate in \
    "$user_directory/anaconda3/bin/conda" \
    "$user_directory/miniconda3/bin/conda" \
    "/opt/homebrew/Caskroom/miniconda/base/bin/conda"; do
    if [[ -x "$candidate" ]]; then
      print -r -- "$candidate"
      return
    fi
  done

  return 1
}

open_workspace() {
  if [[ "${ECON_RESEARCH_NO_OPEN:-0}" != "1" ]]; then
    open "$APP_URL" >/dev/null 2>&1 || true
  fi
}

if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  if curl -fsS "$UI_VERSION_URL" 2>/dev/null | grep -Fq "${UI_VERSION}"; then
    print "Econ Research 已在运行：$APP_URL"
    open_workspace
    exit 0
  fi
  print -u2 "8000 端口已有旧版或其他服务，无法安全打开当前界面。"
  print -u2 "请在运行旧服务的终端按 Control-C 停止它，然后再次双击本启动脚本。"
  exit 1
fi

if ! conda_binary="$(find_conda)"; then
  print -u2 "未找到 Conda。请先安装 Conda，并创建 econ-research 环境。"
  print -u2 "项目目录：$PROJECT_DIR"
  exit 1
fi

if ! "$conda_binary" env list | awk '{print $1}' | grep -qx "econ-research"; then
  print -u2 "未找到 econ-research 环境。请先执行："
  print -u2 "  conda env create -f environment.yml"
  exit 1
fi

wait_and_open() {
  local attempt
  for attempt in {1..80}; do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      print "Econ Research 已启动：$APP_URL"
      open_workspace
      return
    fi
    sleep 0.25
  done
  print -u2 "服务未能在预期时间内启动，请查看终端中的错误信息。"
}

wait_and_open &

print "正在启动 Econ Research…"
print "关闭此终端窗口或按 Control-C 可以停止服务。"

exec "$conda_binary" run --no-capture-output -n econ-research \
  research serve --host 127.0.0.1 --port 8000
