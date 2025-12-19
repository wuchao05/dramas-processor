#!/usr/bin/env python3
"""
FFmpeg 硬件编码器诊断工具
用于检查系统中可用的硬件编码器
"""

import subprocess
import platform
import sys


def run_command(cmd, timeout=10):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True if platform.system() == "Windows" else False
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"
    except Exception as e:
        return -1, "", str(e)


def check_ffmpeg_version():
    """检查 FFmpeg 版本"""
    print("=" * 60)
    print("🔍 检查 FFmpeg 版本")
    print("=" * 60)
    
    code, stdout, stderr = run_command(["ffmpeg", "-version"])
    if code == 0:
        lines = stdout.split('\n')
        if lines:
            print(f"✅ {lines[0]}")
            # 检查编译配置
            for line in lines:
                if "configuration:" in line.lower():
                    if "amf" in line.lower():
                        print("✅ FFmpeg 编译时包含 AMF 支持")
                    else:
                        print("⚠️  FFmpeg 编译时未包含 AMF 支持")
                    break
        return True
    else:
        print("❌ FFmpeg 未安装或不在 PATH 中")
        return False


def check_available_encoders():
    """检查可用的编码器"""
    print("\n" + "=" * 60)
    print("🔍 检查可用的硬件编码器")
    print("=" * 60)
    
    code, stdout, stderr = run_command(["ffmpeg", "-encoders"])
    if code != 0:
        print("❌ 无法获取编码器列表")
        return {}
    
    encoders = {
        "h264_nvenc": "NVIDIA NVENC (H.264)",
        "hevc_nvenc": "NVIDIA NVENC (HEVC)",
        "h264_amf": "AMD AMF (H.264)",
        "hevc_amf": "AMD AMF (HEVC)",
        "h264_qsv": "Intel Quick Sync (H.264)",
        "hevc_qsv": "Intel Quick Sync (HEVC)",
        "h264_videotoolbox": "Apple VideoToolbox (H.264)",
        "hevc_videotoolbox": "Apple VideoToolbox (HEVC)",
        "h264_vaapi": "Linux VA-API (H.264)",
        "hevc_vaapi": "Linux VA-API (HEVC)",
    }
    
    found = {}
    for encoder, name in encoders.items():
        if encoder in stdout:
            print(f"✅ {name:40} ({encoder})")
            found[encoder] = name
        else:
            print(f"❌ {name:40} ({encoder})")
    
    return found


def test_encoder(encoder_name):
    """测试编码器是否真正可用"""
    print(f"\n🧪 测试 {encoder_name}...")
    
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
        "-c:v", encoder_name, "-t", "0.1", "-f", "null", "-"
    ]
    
    code, stdout, stderr = run_command(cmd, timeout=15)
    
    if code == 0:
        print(f"   ✅ {encoder_name} 工作正常")
        return True
    else:
        print(f"   ❌ {encoder_name} 测试失败")
        
        # 分析错误原因
        error_lower = stderr.lower()
        
        if "amf" in encoder_name:
            if any(err in error_lower for err in ["cannot load", "not found", "could not load"]):
                print(f"   💡 可能原因：")
                print(f"      1. FFmpeg 未编译 AMF 支持（需要完整版）")
                print(f"      2. AMD 驱动未正确安装")
                print(f"      3. 缺少 AMF SDK 运行时")
                print(f"\n   🔧 解决方案：")
                print(f"      - 下载完整版 FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases")
                print(f"      - 更新 AMD 驱动到最新版本")
        
        elif "nvenc" in encoder_name:
            if any(err in error_lower for err in ["driver does not support", "required nvenc"]):
                print(f"   💡 可能原因：NVIDIA 驱动版本过旧")
                print(f"   🔧 解决方案：更新 NVIDIA 驱动")
        
        elif "qsv" in encoder_name:
            print(f"   💡 可能原因：Intel 核显未启用或驱动问题")
        
        # 显示部分错误信息
        if stderr:
            error_lines = stderr.split('\n')
            relevant_errors = [line for line in error_lines if any(
                keyword in line.lower() for keyword in 
                ["error", "failed", "cannot", "not found", "not supported"]
            )]
            if relevant_errors:
                print(f"\n   📋 错误详情：")
                for line in relevant_errors[:3]:  # 只显示前3行
                    print(f"      {line.strip()}")
        
        return False


def check_system_info():
    """显示系统信息"""
    print("\n" + "=" * 60)
    print("💻 系统信息")
    print("=" * 60)
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"架构: {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")


def main():
    """主函数"""
    print("\n" + "🎬" * 20)
    print("FFmpeg 硬件编码器诊断工具")
    print("🎬" * 20 + "\n")
    
    check_system_info()
    
    if not check_ffmpeg_version():
        print("\n❌ 请先安装 FFmpeg")
        return
    
    found_encoders = check_available_encoders()
    
    if not found_encoders:
        print("\n⚠️  未找到任何硬件编码器")
        print("\n💡 建议：")
        print("   1. 下载完整版 FFmpeg（包含所有编码器支持）")
        print("   2. 确保显卡驱动已正确安装")
        return
    
    # 测试找到的编码器
    print("\n" + "=" * 60)
    print("🧪 测试硬件编码器实际可用性")
    print("=" * 60)
    
    working_encoders = []
    for encoder in found_encoders.keys():
        if test_encoder(encoder):
            working_encoders.append(encoder)
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 诊断总结")
    print("=" * 60)
    
    if working_encoders:
        print(f"✅ 可用的硬件编码器: {len(working_encoders)} 个")
        for encoder in working_encoders:
            print(f"   - {encoder}")
        print(f"\n💡 建议在配置文件中使用: {working_encoders[0]}")
    else:
        print("❌ 没有可用的硬件编码器")
        print("💡 建议使用软件编码: libx264")
        print("   命令行参数: --sw")


if __name__ == "__main__":
    main()
