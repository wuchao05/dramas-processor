#!/usr/bin/env python3
"""Windows 环境测试脚本"""
import os
import sys
import subprocess
from pathlib import Path


def test_ffmpeg():
    """测试 FFmpeg"""
    print("[1/5] 测试 FFmpeg...")
    try:
        from drama_processor.utils.ffmpeg import find_ffmpeg, find_ffprobe
        ffmpeg = find_ffmpeg()
        ffprobe = find_ffprobe()
        
        result = subprocess.run([ffmpeg, "-version"], 
                              capture_output=True, text=True,
                              timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0] if result.stdout else "未知版本"
            print(f"  ✅ FFmpeg: {ffmpeg}")
            print(f"     版本: {version_line}")
            return True
        else:
            print(f"  ❌ FFmpeg 无法运行")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_font():
    """测试字体检测"""
    print("[2/5] 测试字体检测...")
    try:
        from drama_processor.models.config import ProcessingConfig
        config = ProcessingConfig()
        font = config.get_default_font()
        
        if font and os.path.exists(font):
            print(f"  ✅ 字体: {font}")
            return True
        else:
            print(f"  ❌ 字体文件不存在: {font}")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_temp_dir():
    """测试临时目录"""
    print("[3/5] 测试临时目录...")
    try:
        from drama_processor.utils.files import ensure_temp_root
        temp_dir = ensure_temp_root(None)
        
        if os.path.exists(temp_dir):
            print(f"  ✅ 临时目录: {temp_dir}")
            return True
        else:
            print(f"  ❌ 临时目录创建失败")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_config():
    """测试配置加载"""
    print("[4/5] 测试配置加载...")
    try:
        # 尝试加载 Windows 配置
        config_path = "configs/windows_default.yaml"
        if not os.path.exists(config_path):
            config_path = "configs/default.yaml"
        
        from drama_processor.models.config import ProcessingConfig
        config = ProcessingConfig.from_yaml(config_path)
        print(f"  ✅ 配置加载成功: {config_path}")
        print(f"     源目录: {config.default_source_dir}")
        return True
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_cli():
    """测试 CLI 命令"""
    print("[5/5] 测试 CLI...")
    try:
        result = subprocess.run(["drama-processor", "--help"],
                              capture_output=True, text=True,
                              timeout=10)
        if result.returncode == 0:
            print(f"  ✅ CLI 可用")
            return True
        else:
            print(f"  ❌ CLI 返回错误码: {result.returncode}")
            return False
    except FileNotFoundError:
        print(f"  ⚠️  CLI 命令未安装（开发环境请先运行 pip install -e .)")
        return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def main():
    print("=" * 70)
    print("Drama Processor Windows 环境测试")
    print("=" * 70)
    print("")
    
    # 检测平台
    import platform
    system = platform.system()
    print(f"操作系统: {system}")
    print(f"Python 版本: {sys.version}")
    print("")
    
    if system != "Windows":
        print(f"⚠️  警告: 当前系统不是 Windows ({system})")
        print(f"   但测试仍会继续（跨平台兼容性测试）")
        print("")
    
    # 运行所有测试
    results = [
        test_ffmpeg(),
        test_font(),
        test_temp_dir(),
        test_config(),
        test_cli(),
    ]
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ 全部通过 ({passed}/{total})")
        print("")
        print("恭喜！环境配置正确，可以开始使用。")
        print("")
        print("下一步:")
        print("  1. 修改配置文件: configs/windows_default.yaml")
        print("  2. 运行 GUI: python run_gui.py")
        print("  3. 或使用 CLI: drama-processor --help")
        sys.exit(0)
    else:
        print(f"❌ 部分失败 ({passed}/{total})")
        print("")
        print("请检查失败的项目并修复后重试。")
        print("")
        print("常见问题:")
        print("  - FFmpeg: 确保 bin/ffmpeg.exe 和 bin/ffprobe.exe 存在")
        print("  - 字体: Windows 系统应自动检测，如失败请检查 C:\\Windows\\Fonts")
        print("  - CLI: 开发环境需要先运行 pip install -e .")
        sys.exit(1)


if __name__ == "__main__":
    main()
