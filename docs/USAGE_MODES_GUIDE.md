# 使用模式指南：源码 / Lite 包 / Pro 包

本文说明三种常见使用方式，以及每种方式的配置方法与功能范围。

---

## 0. 通用前置条件（所有模式都需要）

- **系统**：Windows + WSL（Arch/Ubuntu 均可）。  
- **FFmpeg**：必须安装，且命令行可用。  
  - Arch/WSL：`sudo pacman -S ffmpeg`
  - Ubuntu/WSL：`sudo apt-get install ffmpeg`
  - 验证：`ffmpeg -version`
- **素材目录结构**：短剧根目录下每部剧一个文件夹，里面是 `01.mp4/02.mp4/...` 等集文件。
- **资源**：尾部视频默认 `assets/tail.mp4`；若关闭尾部或无该文件会自动跳过。

---

## 0.1 发布包（Lite/Pro）机器绑定授权流程（重要）

Lite/Pro 的**打包后二进制发布包**默认启用“机器绑定授权”，用于防止朋友把包转发给其他人使用。

机制说明：

- 你本地保存 **Ed25519 私钥**，用于签发 `license.json`（不要发给任何人）。
- 程序内置 **Ed25519 公钥**，用于验签 `license.json`。
- `license.json` 里包含 `machine_fingerprint`（机器指纹），发布包运行时必须与当前机器匹配。

一次性准备（你只需做一次）：

1. 生成密钥对：

```bash
python scripts/license_tool.py gen-keys
```

2. 把公钥 `license_keys/ed25519_public.pem` 的 PEM 内容复制到  
   `src/drama_processor/utils/license.py` 的 `DEFAULT_PUBLIC_KEY_PEM`，然后重新出包（否则发布包无法验签）。

给朋友发包（每台机器都要做一次）：

1. 你先把 Lite/Pro 包发给朋友（此时朋友只能做“打印指纹”操作）。
2. 朋友在发布包目录执行（不需要 license）：

```bash
./drama-processor-lite --print-fingerprint
# 或 Pro：./drama-processor --print-fingerprint
```

3. 朋友把输出的指纹发给你。
4. 你用私钥签发绑定该指纹的 `license.json`，并发回给朋友。
5. 朋友把 `license.json` 放到二进制同目录（推荐），程序会自动识别，无需每次传参：

```
lite_release/
  drama-processor-lite
  license.json
```

没有 license 会怎样？

- 发布包（二进制）下：除了 `--print-fingerprint` 外，其他命令会直接退出并提示缺少/无效 license。

---

## 1. 在源码下直接执行剪辑（开发/自用）

### 1.1 安装与运行

在仓库根目录：

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

之后即可在仓库根目录直接运行命令（不需要打包）：

```bash
# Lite 行为（无 Feishu）
drama-processor-lite process /mnt/d/短剧剪辑/源素材视频

# Pro 行为（全功能，Feishu 需授权或 dev bypass）
drama-processor process /mnt/d/短剧剪辑/源素材视频
```

也可用模块方式（临时调试）：

```bash
python -m drama_processor.cli.lite_main process
python -m drama_processor.cli.main process
```

### 1.2 配置方式

- **Lite 源码运行**：不传 `-c` 时会优先用 `configs/lite.yaml`（存在则生效）。  
- **Pro 源码运行**：不传 `-c` 时会优先用 `configs/pro.yaml`，找不到再回退 `configs/default.yaml`。  
  - 但当你设置了 `DRAMA_PROCESSOR_DEV_BYPASS=1`（源码调试 Feishu）时，会强制优先使用 `configs/default.yaml`，避免误用面向发布包的 `pro.yaml`。
- 你可以通过 `-c/--config` 指定任意配置文件：

```bash
drama-processor-lite -c configs/lite.yaml process
drama-processor -c configs/pro.yaml process
```

### 1.3 功能范围

- **本地剪辑/分析/历史/配置**：`process`、`analyze`、`history`、`config` 全部可用，不需要 license。
- **Feishu（Pro）**：
  - 正常情况下必须提供 license（见第 3 节）。
  - **开发旁路**：源码运行时可以设置环境变量跳过 license 校验：

```bash
export DRAMA_PROCESSOR_DEV_BYPASS=1
drama-processor feishu list
```

该旁路 **仅对源码运行有效**，对二进制无效。

---

## 2. 打包 Lite 版本并使用（对外分发，无 Feishu）

Lite 版用于对外给朋友使用：保留除 Feishu 外的所有功能，且运行时强制关闭 Feishu。

### 2.0 发布包机器绑定（重要）

Lite 包的机器绑定流程同 0.1，这里按时间顺序再写一遍（方便直接照做）：

1. 你先生成并发给朋友 `lite_release/`。
2. 朋友执行并把指纹发你：

```bash
./drama-processor-lite --print-fingerprint
```

3. 你签发（Lite 建议 features 不包含 feishu）：

```bash
python scripts/license_tool.py sign \
  --private-key license_keys/ed25519_private.pem \
  --user friend-a \
  --features process,analyze,config,history \
  --machine-fingerprint <朋友发来的指纹> \
  --expires-at 2026-01-01 \
  --out license.json
```

4. 朋友把 `license.json` 放到 `lite_release/`（与二进制同级），然后才能运行 `process/analyze/history/config`。

### 2.1 生成 Lite 包

在 WSL/Linux 的仓库根目录（已激活 `.venv`）：

```bash
bash scripts/make_lite_release_wsl.sh --clean
```

产物：

- 发布目录：`lite_release/`
- 压缩包：`drama-processor-lite-*-wsl.zip` 或 `.tar.gz`

发布目录结构：

```
lite_release/
  drama-processor-lite
  assets/              # 脚本会自动去掉 watermark-*
  configs/
    lite.yaml          # 朋友专属配置写在这里
```

### 2.2 配置方式

- Lite 包**只使用 `configs/lite.yaml`**（不依赖 `users/`）。
- `lite.yaml` 内需要写入朋友机器的必填项（至少要改）：
  - `default_source_dir`
  - `backup_source_dir`（必须是字符串；不需要备份可填同路径）
  - `count` / `material_code`
  - `title_colors`
  - `brand_text_mapping`
- 运行时可以用参数覆盖配置：

```bash
./drama-processor-lite process --count 5 --out-dir /mnt/d/导出素材
```

### 2.3 朋友使用方式

在朋友 WSL 内：

```bash
sudo apt-get install ffmpeg   # Ubuntu

cd lite_release
chmod +x drama-processor-lite
# 发布包运行需要 license（机器绑定）：
# 1) 先打印指纹发给你签发 license：./drama-processor-lite --print-fingerprint
# 2) 将你签发的 license.json 放到本目录（与二进制同级）
./drama-processor-lite process
```

### 2.4 功能范围

- 可用：`process`、`analyze`、`history`、`config`、隐藏的 `run`。  
- 不可用：任何 `feishu ...` 命令（不会出现在 `--help` 里）。  
- 发布包运行需要 license（用于机器绑定；即便 license 的 `features` 包含 `feishu`，Lite 也不会开放 Feishu）。

---

## 3. 打包 Pro 版本并使用（全功能，Feishu 需 license）

Pro 版用于自用或后续给朋友升级到 Feishu 能力。

### 3.1 生成 Pro 包

在 WSL/Linux 的仓库根目录：

```bash
bash scripts/make_pro_release_wsl.sh --clean --pro-config configs/pro.yaml
```

产物：

```
pro_release/
  drama-processor
  assets/
  configs/
    pro.yaml
```

### 3.2 License 生成与使用

Pro 发布包运行同样受“机器绑定授权”约束（见 0.1），这里补充签发示例与 Feishu 授权说明。

给自己签发（绑定当前机器）：

```bash
python scripts/license_tool.py sign \
  --private-key license_keys/ed25519_private.pem \
  --user me \
  --features process,analyze,config,history,feishu \
  --bind-current-machine \
  --expires-at 2026-01-01 \
  --out license.json
```

给朋友签发（绑定朋友机器）：

```bash
./drama-processor --print-fingerprint
```

把输出的指纹发给你，然后你用：

```bash
python scripts/license_tool.py sign \
  --private-key license_keys/ed25519_private.pem \
  --user friend-a \
  --features process,analyze,config,history,feishu \
  --machine-fingerprint <朋友发来的指纹> \
  --expires-at 2026-01-01 \
  --out license.json
```

使用 license（三种方式任选其一）：

```bash
# 方式 A：把 license.json 放在二进制同目录（推荐，自动识别）

# 方式 B：命令行参数（必须放在子命令前）
./drama-processor --license /path/to/license.json feishu list

# 方式 C：环境变量
export DRAMA_PROCESSOR_LICENSE=/path/to/license.json
./drama-processor feishu run
```

> 注意：如果 license 的 `features` 不包含 `feishu`（或 `*`），则 Pro 仍可做本地剪辑，但 `feishu` 命令会被隐藏/禁用。

### 3.3 配置方式

- Pro 二进制不传 `-c` 时，会优先找 `configs/pro.yaml`（存在则用）。
- 推荐把飞书凭据写在发布包内的 `configs/pro.yaml`（不要用你的 `configs/users/*.yaml` 直接复制给别人）。

### 3.4 功能范围

- 发布包运行：必须有 license（机器绑定），否则无法启动。
- license 的 `features` 决定是否允许 Feishu：
  - 包含 `feishu` 或 `*`：`feishu list/run/watch/dedup` 可用。
  - 不包含 `feishu`：仍可用 `process/analyze/history/config`，但 `feishu` 会被隐藏/禁用。

---

## 4. 配置覆盖优先级（所有模式一致）

从低到高：

1. 代码内置默认值（`ProcessingConfig`）  
2. 配置文件（`-c` 指定或默认搜索到的 YAML）  
3. 命令行参数（如 `--count/--out-dir/--date`）  

---

## 5. 常见问题

- **为什么二进制找不到 `assets/tail.mp4`？**  
  旧包会在 `/tmp/_MEI...` 里找资源；已在新版修复。重新出包即可。
- **`backup_source_dir` 能否写 null？**  
  不能，必须是字符串。无需备份时可填与主目录一致。
- **加 `--date 11.12` 后导出目录名是什么？**  
  会创建 `11.12导出/`（新版已修复）。
