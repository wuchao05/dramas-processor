# GUI 现代化升级说明

## 🎨 升级内容

已将原有的 Tkinter GUI 升级为基于 **CustomTkinter** 的现代化界面。

### 主要改进

1. **现代化外观**
   - 深色主题（支持深色/浅色/系统自动）
   - 圆角控件和卡片式设计
   - 更好的配色方案和对比度

2. **视觉优化**
   - 添加 Emoji 图标增强可读性
   - 改进间距和布局
   - 更大更清晰的按钮和文字
   - 平滑的进度条动画

3. **交互改进**
   - 更明显的按钮状态（悬停效果）
   - 优化的滚动区域
   - 更清晰的分组和视觉层次

## 📦 安装依赖

```bash
# 安装 CustomTkinter
pip install customtkinter>=5.2.0

# 或者重新安装所有依赖
pip install -r requirements.txt
```

## 🚀 运行 GUI

### 方式一：通过 Python 模块
```bash
python -m drama_processor.gui
```

### 方式二：通过脚本入口
```bash
python scripts/gui_entry.py
```

### 方式三：安装后直接运行
```bash
# 如果已安装 drama_processor 包
drama-processor-gui  # 如果配置了该入口点
```

## 🎯 主要特性

### 深色模式
默认使用深色主题，可以在代码中修改：
```python
# 在 DramaProcessorGUI.__init__ 中修改
ctk.set_appearance_mode("dark")   # "dark" / "light" / "system"
ctk.set_default_color_theme("blue")  # "blue" / "green" / "dark-blue"
```

### 主题颜色
- **主按钮（开始处理）**: 蓝色系 `#1f6aa5`
- **取消按钮**: 红色系 `#d32f2f`
- **背景色**: 深色 `#2b2b2b`
- **强调色**: 系统蓝色

### 布局特点
- **响应式布局**: 窗口可自由调整大小
- **滚动支持**: 主窗口支持滚动，适配小屏幕
- **分区清晰**: 使用卡片式设计分隔不同功能区

## 🔧 自定义配置

### 修改主题色
在 `app.py` 第 126 行修改：
```python
ctk.set_default_color_theme("green")  # 改为绿色主题
```

### 修改外观模式
```python
ctk.set_appearance_mode("light")  # 改为浅色模式
```

### 修改窗口大小
在 `app.py` 第 129 行修改：
```python
self.geometry("1200x900")  # 调整初始窗口大小
self.minsize(1000, 800)    # 调整最小窗口大小
```

## 📋 功能清单

✅ 保留了所有原有功能
✅ 基础设置（素材目录、配置文件、输出目录、字体文件）
✅ 剧目选择（搜索、多选、批量操作）
✅ 处理参数配置
✅ 用户配置（素材标识、标题颜色、品牌文案）
✅ 实时日志显示
✅ 进度追踪
✅ 取消处理功能

## 🐛 已知问题

- Listbox 控件仍使用原生 Tkinter（CustomTkinter 没有直接替代品）
- macOS 系统对话框样式保持系统原生

## 📸 视觉效果对比

### 改进前
- 朴素的灰白色界面
- 方角控件
- 简单的扁平设计

### 改进后
- 现代化深色主题
- 圆角卡片设计
- 更好的视觉层次
- Emoji 图标点缀
- 更清晰的按钮状态

## 🔄 回退方案

如果遇到兼容性问题，可以回退到原版本：
```bash
git checkout HEAD~1 -- src/drama_processor/gui/app.py
pip uninstall customtkinter
```

## 💡 未来改进方向

1. 添加主题切换按钮（让用户动态切换深色/浅色）
2. 支持自定义主题颜色
3. 添加更多动画效果
4. 优化 Listbox 为自定义控件
5. 添加配置预设保存/加载功能
6. 添加快捷键支持

## 🤝 反馈

如有问题或建议，欢迎反馈！

