# 🤖 AI 功能安装和使用指南（简化版本）

> **注意**: 这是简化版本的 AI 功能，暂时移除了视频质量评估、文字内容检测、音频内容检测等功能，专注于核心的场景检测和基础视觉合规检测。

## 📋 **安装步骤**

### **1. 安装 AI 依赖**

```bash
# 进入项目目录
cd dramas_processor

# 安装AI功能依赖
pip install -r requirements_ai.txt

# 如果需要GPU加速（可选）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### **2. 安装可选依赖**

```bash
# 音频处理（用于对话停顿检测）
pip install librosa

# OCR文字识别（用于敏感文字检测）
pip install pytesseract

# 安装Tesseract OCR引擎
# macOS:
brew install tesseract tesseract-lang

# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim

# Windows:
# 下载并安装 https://github.com/UB-Mannheim/tesseract/wiki
```

### **3. 下载 AI 模型**

```bash
# 使用内置模型下载器
python -m src.drama_processor.ai.models.model_downloader --list

# 下载场景分类模型
python -m src.drama_processor.ai.models.model_downloader scene_classifier

# 下载内容安全模型
python -m src.drama_processor.ai.models.model_downloader content_safety
```

---

## ⚙️ **配置设置**

### **1. 启用 AI 功能**

编辑 `configs/ai_config.yaml`：

```yaml
# 启用AI功能
ai_enabled: true

# 启用场景检测
scene_detection:
  enabled: true
  quality_threshold: 0.6

# 启用内容合规检测
compliance_check:
  enabled: true
  strict_mode: false # 建议先设为false进行测试
```

### **2. 性能优化配置**

```yaml
performance:
  max_concurrent_analysis: 2 # 根据CPU核心数调整
  gpu_acceleration: false # 有GPU时可设为true
  memory_limit_mb: 2048 # 根据可用内存调整
```

---

## 🎯 **使用方法**

### **1. 基础使用**

```bash
# 启用AI场景检测
drama-processor process /path/to/dramas --ai-scene-detection

# 启用内容合规检测
drama-processor process /path/to/dramas --ai-compliance-check

# 同时启用两个功能
drama-processor process /path/to/dramas --ai-scene-detection --ai-compliance-check
```

### **2. 高级配置**

```bash
# 使用自定义AI配置文件
drama-processor process /path/to/dramas --ai-config configs/custom_ai.yaml

# 严格合规模式（不合规内容直接拒绝）
drama-processor process /path/to/dramas --ai-compliance-check --strict-compliance
```

### **3. 分析模式**

```bash
# 仅分析不处理（查看AI分析结果）
drama-processor analyze /path/to/dramas --ai-analysis

# 生成详细的合规报告
drama-processor analyze /path/to/dramas --compliance-report
```

---

## 📊 **功能说明**

### **🎬 智能场景检测**

**作用：**

- 自动识别视频中的场景变化点
- 评估每个场景的视觉质量
- 推荐最佳的剪辑起始和结束点
- 避免在场景中间进行剪切

**工作原理：**

1. **场景变化检测**：通过分析连续帧的直方图差异识别场景切换
2. **质量评估**：评估清晰度、亮度、对比度等视觉质量指标
3. **剪辑点优化**：结合场景边界和质量评分推荐最佳剪辑点

**输出结果：**

```json
{
  "scenes": [
    {
      "start_time": 0.0,
      "end_time": 15.2,
      "quality_score": 0.85,
      "scene_type": "dialogue"
    }
  ],
  "optimal_cut_points": [
    {
      "timestamp": 15.2,
      "confidence": 0.92,
      "cut_type": "scene_change"
    }
  ]
}
```

### **🛡️ 内容合规检测**

**作用：**

- 检测视频中的暴力、成人等敏感内容
- 识别音频中的敏感词汇
- 通过 OCR 检测画面文字中的敏感内容
- 生成安全片段推荐

**检测类型：**

| 检测类型 | 技术方案                    | 风险等级 |
| -------- | --------------------------- | -------- |
| 暴力内容 | 红色区域检测 + 边缘密度分析 | 高风险   |
| 成人内容 | 肤色区域比例检测            | 禁止     |
| 敏感文字 | OCR + 关键词匹配            | 中风险   |
| 音频内容 | 音量异常检测                | 低风险   |

**输出报告：**

```json
{
  "overall_risk": "low_risk",
  "issues": [
    {
      "timestamp": 120.5,
      "type": "dark_scene",
      "risk_level": "low_risk",
      "confidence": 0.6,
      "description": "场景过暗，可能影响观看体验"
    }
  ],
  "safe_segments": [
    [0.0, 115.0],
    [125.0, 300.0]
  ]
}
```

---

## 🔧 **故障排除**

### **常见问题**

**1. 模型下载失败**

```bash
# 手动指定代理
export https_proxy=http://proxy:port
python -m src.drama_processor.ai.models.model_downloader scene_classifier --force
```

**2. 内存不足**

```yaml
# 调整配置文件
performance:
  memory_limit_mb: 1024 # 减少内存使用
  max_concurrent_analysis: 1 # 减少并发数
```

**3. GPU 加速不工作**

```bash
# 检查CUDA是否正确安装
python -c "import torch; print(torch.cuda.is_available())"

# 重新安装GPU版本的PyTorch
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**4. OCR 识别失败**

```bash
# 检查Tesseract安装
tesseract --version

# 检查中文语言包
tesseract --list-langs | grep chi
```

### **性能调优建议**

**1. CPU 优化**

```yaml
performance:
  max_concurrent_analysis: 4 # 设为CPU核心数
  memory_limit_mb: 4096 # 增加内存限制
```

**2. 采样频率调整**

```yaml
scene_detection:
  sample_rate: 0.5 # 降低采样率以提高速度

compliance_check:
  sample_interval: 10.0 # 增加采样间隔
```

**3. 功能选择性启用**

```yaml
compliance_check:
  checks:
    visual_content: true # 保留核心功能
    audio_content: false # 禁用耗时的音频检测
    text_content: false # 禁用OCR检测
```

---

## 📈 **效果验证**

### **测试 AI 功能**

```bash
# 1. 基础功能测试
drama-processor test-ai --scene-detection --test-video test_video.mp4

# 2. 合规检测测试
drama-processor test-ai --compliance-check --test-video test_video.mp4

# 3. 性能测试
drama-processor benchmark --ai-features --duration 60
```

### **预期改进效果**

| 功能     | 改进指标     | 预期提升 |
| -------- | ------------ | -------- |
| 场景检测 | 剪辑点质量   | 40%+     |
| 内容合规 | 风险识别率   | 85%+     |
| 整体效率 | 人工审核时间 | -60%     |
| 素材质量 | 观众留存率   | +25%     |

---

## 🔮 **后续扩展**

### **计划中的功能**

1. **智能标题生成**：基于视频内容自动生成吸引人的标题
2. **情感分析增强**：更精确的情感识别和匹配
3. **实时处理**：支持实时视频流的 AI 分析
4. **自定义模型训练**：基于用户数据训练专门的检测模型

### **集成第三方服务**

```yaml
# 未来可能的配置
external_services:
  content_moderation_api: "阿里云内容安全API"
  speech_recognition: "百度语音识别API"
  scene_understanding: "腾讯云视频AI"
```

---

## 💡 **最佳实践**

1. **渐进式启用**：先启用场景检测，稳定后再启用合规检测
2. **阈值调优**：根据实际内容调整检测阈值
3. **人工验证**：AI 结果应结合人工审核
4. **定期更新**：保持模型和敏感词库的更新
5. **性能监控**：监控 AI 功能对整体性能的影响

开始使用 AI 功能，让你的短剧处理更智能！🚀
