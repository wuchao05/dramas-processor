# FFmpeg Windows 可执行文件目录

此目录用于存放 FFmpeg Windows 版本的可执行文件。

## 下载说明

1. 访问: https://www.gyan.dev/ffmpeg/builds/
2. 下载: ffmpeg-release-essentials.zip
3. 解压后，将以下文件复制到此目录:
   - ffmpeg.exe
   - ffprobe.exe

## 版本要求

推荐使用最新的 release 版本。
最低要求: FFmpeg 4.0+

## 文件列表

此目录应包含:
- ffmpeg.exe  (视频处理主程序)
- ffprobe.exe (视频信息探测工具)
- README.txt  (本文件)

## 验证安装

在命令行运行:
```
bin\ffmpeg.exe -version
bin\ffprobe.exe -version
```

应该能看到版本信息输出。

## 注意事项

- 这些文件仅在 Windows 环境下使用
- 文件大小约 80-100MB
- 已添加到 .gitignore，不会提交到仓库
