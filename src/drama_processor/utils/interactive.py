"""Interactive selection utilities."""

import os
import sys
from typing import List, Optional, Set


def interactive_pick_dramas(all_drama_dirs: List[str], excludes: Optional[Set[str]] = None) -> List[str]:
    """Interactive drama selection with fuzzy search support."""
    names = [os.path.basename(d.rstrip("/")) for d in all_drama_dirs]
    if excludes:
        names = [n for n in names if n not in excludes]
    if not names:
        return []
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return []

    try:
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice

        keybindings = {
            "toggle": [{"key": " "}],
            "down":   [{"key": "down"}, {"key": "c-n"}],
            "up":     [{"key": "up"},   {"key": "c-p"}],
        }

        result = inquirer.fuzzy(
            message=(
                "选择要处理的短剧：\n"
                "  - 直接输入=模糊搜索（插入模式）\n"
                "  - ESC 进入普通模式，用 j/k 或 ↑/↓ 移动；i 返回输入\n"
                "  - 空格多选，回车确认"
            ),
            choices=[Choice(name, name) for name in names],
            multiselect=True,
            keybindings=keybindings,
            vi_mode=True,
            instruction="提示：ESC 切换到普通模式用 j/k；i 返回输入；空格选中；回车确认",
        ).execute()

        if not result:
            return []
        if isinstance(result, str):
            result = [result]
        picked_names = [str(x) for x in result]
        name_to_dir = {os.path.basename(d.rstrip("/")): d for d in all_drama_dirs}
        return [name_to_dir[n] for n in picked_names if n in name_to_dir]

    except Exception as e:
        import traceback
        print("⚠️ InquirerPy 交互 UI 启动失败，降级数字多选：", repr(e))
        traceback.print_exc()
        
        # Fallback to numbered selection
        for i, n in enumerate(names, 1):
            print(f"{i:2d}. {n}")
        raw = input("输入要处理的序号（逗号分隔），留空=全选：").strip()
        
        if not raw:
            picked = names
        else:
            picked = []
            for tok in raw.split(","):
                tok = tok.strip()
                if tok.isdigit():
                    idx = int(tok)
                    if 1 <= idx <= len(names):
                        picked.append(names[idx-1])
        
        name_to_dir = {os.path.basename(d.rstrip("/")): d for d in all_drama_dirs}
        return [name_to_dir[n] for n in picked if n in name_to_dir]
