#!/bin/bash

# 飞书剧列表剪辑常用别名
# 使用方法: source feishu_aliases.sh 或添加到 ~/.zshrc

# 主命令（支持子命令和参数传递）
fscut() {
    if [ $# -eq 0 ]; then
        # 无参数时默认执行 run
        ./feishu_quick.sh run
    else
        # 有参数时直接传递给 feishu_quick.sh
        ./feishu_quick.sh "$@"
    fi
}

# 保留单独的子命令别名（向后兼容）
fscutselect() { ./feishu_quick.sh select "$@"; } # 交互选择剧目（支持参数）
fscutlist() { ./feishu_quick.sh list "$@"; }     # 查看待处理列表（支持参数）

# 常用组合别名
alias fscutfast='./feishu_quick.sh run --fast --jobs 4'           # 快速处理（4并发）
alias fscutquick='./feishu_quick.sh select --fast --jobs 2'       # 快速选择（2并发）
alias fscutpreview='./feishu_quick.sh select --status "待剪辑"'     # 预览待处理剧目
alias fscuthigh='./feishu_quick.sh run --jobs 4 --count 15'       # 高产出（15条/剧，4并发）

# 状态查看别名
alias fscut待剪辑='./feishu_quick.sh list --status 待剪辑'
alias fscut剪辑中='./feishu_quick.sh list --status 剪辑中'
alias fscut待上传='./feishu_quick.sh list --status 待上传'

# 显示所有别名
alias fscuthelp='echo "
飞书剧列表剪辑别名（所有命令都支持参数）:
  fscut        - 主命令（无参数时默认run）
  fscut run    - 剪辑处理所有待剪辑
  fscut select - 交互选择剧目
  fscut list   - 查看待处理列表
  
向后兼容别名:
  fscutselect  - 等同于 fscut select
  fscutlist    - 等同于 fscut list
  
常用组合:
  fscutfast    - 快速处理（4并发）
  fscutquick   - 快速选择（2并发）  
  fscutpreview - 预览待处理剧目
  fscuthigh    - 高产出（15条/剧）
  
状态查看:
  fscut待剪辑   - 查看待剪辑列表
  fscut剪辑中   - 查看剪辑中列表
  fscut待上传   - 查看待上传列表

参数使用示例:
  fscut                          - 默认运行剪辑处理
  fscut run --date \"9.4\"         - 处理特定日期的剧目
  fscut run --jobs 8 --count 20  - 8并发处理，每剧20条
  fscut select --fast            - 快速选择模式
  fscut list --status 待剪辑      - 查看待剪辑状态
  fscut sync --dry-run           - 预览同步模式
"'

echo "🎬 飞书剧列表剪辑别名已加载"
echo "💡 输入 'fscuthelp' 查看所有可用别名"
