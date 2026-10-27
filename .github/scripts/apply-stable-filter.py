
from pathlib import Path
import re
import sys

target = Path("sing-box.sh")

if not target.is_file():
    sys.exit("错误：找不到 sing-box.sh，停止修改。")

content = target.read_text(encoding="utf-8")

# 替换默认备用版本，避免预设值是 alpha 版。
content, count = re.subn(
    r"(?m)^DEFAULT_NEWEST_VERSION=.*$",
    "DEFAULT_NEWEST_VERSION=''",
    content,
    count=1,
)

if count != 1:
    sys.exit("错误：未找到唯一的 DEFAULT_NEWEST_VERSION，停止修改。")

# 同时处理 force_version、Atom 和 GitHub API 三种版本来源。
new_function = r'''# 获取最新的正式稳定版 sing-box
get_sing_box_version() {
  local FORCE_VERSION RESULT_VERSION

  # 只接受纯正式版本号；上游强制指定的预发布版一律忽略
  FORCE_VERSION=$(wget --no-check-certificate --tries=2 --timeout=3 -qO- "${GH_PROXY}https://raw.githubusercontent.com/fscarmen/sing-box/refs/heads/main/force_version" 2>&1 | sed 's/^[vV]//g; s/\r//g')

  if [[ "$FORCE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    RESULT_VERSION="$FORCE_VERSION"
  else
    # 优先从 Atom 获取，只保留 x.y.z 格式的正式版本
    RESULT_VERSION=$(wget --no-check-certificate --tries=2 --timeout=3 -qO- "${GH_PROXY}https://github.com/SagerNet/sing-box/releases.atom" 2>&1 \
      | sed -n '/alternate/ s#.*/tag/v\([^"]\+\)".*#\1#gp' \
      | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
      | sort -Vr | head -n 1)

    # Atom 没有可用的稳定版本时，使用 GitHub latest API
    if [ -z "$RESULT_VERSION" ]; then
      RESULT_VERSION=$(wget --no-check-certificate --tries=2 --timeout=3 -qO- "${GH_PROXY}https://api.github.com/repos/SagerNet/sing-box/releases/latest" 2>&1 \
        | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"v\{0,1\}\([^"]*\)".*/\1/p' \
        | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -n 1)
    fi
  fi

  # 没有找到正式版本时返回空值，由原脚本处理错误；绝不回退到预发布版
  echo "$RESULT_VERSION"
}'''

pattern = r"(?ms)^get_sing_box_version\(\) \{\n.*?^\}"
content, count = re.subn(pattern, lambda _: new_function, content, count=1)

if count != 1:
    sys.exit("错误：未能唯一定位 get_sing_box_version()，停止修改。")

target.write_text(content, encoding="utf-8")
print("已应用稳定版筛选规则。")
