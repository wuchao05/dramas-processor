# AGENTS Guide

本文件是本仓库唯一保留的代理规范入口。

仓库内原有 `CLAUDE.md` 规则已并入此文件。

当前未发现以下额外代理规则文件：
- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`

如果后续新增这些文件，应与本文件保持一致，避免规则冲突。

## Communication
- 使用中文回复。
- 说明、总结、提交信息建议、代码注释默认都使用中文，除非用户明确要求英文。
- 回答要直接、可执行，先给结论，再补充必要上下文。

## Workflow
- 始终在 `master` 分支上进行代码修改：所有代码变更必须直接在 `master` 分支上完成，不使用功能分支，除非用户明确要求。
- 自动提交并推送：每次修改代码后自动提交并推送到远程 `master` 分支；只有当用户明确说明需要 review 代码时，才不自动提交和推送。
- 工作流程：
  1. 确认当前在 `master` 分支：`git branch --show-current`
  2. 进行代码修改
  3. 运行 lint 和 type-check
  4. 提交代码到 `master` 分支
  5. 立即推送到远程：`git push origin master`
- 每次解决完问题后，简要说明接下来可能需要的改动和优化建议。

## Agent Priorities
- 先读仓库现有实现和配置，再动手，不要靠猜。
- 优先做最小充分修改，避免顺手重构无关代码。
- 不要擅自删除用户已有改动，也不要覆盖工作区中与你任务无关的变更。
- 如果用户要的是分析、解释、排查，就先给分析，不要直接实现。

## Repository Layout
- 核心包位于 `src/drama_processor/`。
- CLI 入口在 `src/drama_processor/cli/`，主脚本由 `pyproject.toml` 中的 `drama-processor` 和 `drama-processor-lite` 暴露。
- 核心处理流程在 `src/drama_processor/core/`，如 `processor.py`、`encoder.py`、`overlay.py`、`analyzer.py`。
- 配置模型、加载器、日志与工具分别位于 `src/drama_processor/models/`、`src/drama_processor/config/`、`src/drama_processor/utils/`。
- 飞书相关集成位于 `src/drama_processor/integrations/`。
- GUI 代码位于 `src/drama_processor/gui/` 与根目录 `run_gui.py`。
- 默认配置文件是 `configs/default.yaml`，用户级配置位于 `configs/users/`。
- 静态资源位于 `assets/`，打包脚本在 `packaging/`、`scripts/` 与若干根目录脚本中。

## Setup And Build
- Python 版本要求来自 `pyproject.toml`：`>=3.8`。
- 安装运行时依赖：`pip install -r requirements.txt`
- 安装开发依赖：`pip install -e ".[dev]"`
- 如果只需要本地可编辑安装，也可以使用：`pip install -e .`
- 本仓库使用 `setuptools.build_meta` 作为构建后端。
- 若要构建源码包和 wheel，优先使用：`python -m build`
- 如果本机未安装 `build`，先执行：`pip install build`
- 常用 CLI 自检命令：`drama-processor --help`、`drama-processor-lite --help`
- Windows 打包和发布辅助脚本位于根目录 `package.ps1`、`package-tool.ps1`、`package.sh` 以及 `packaging/`。
- 变更打包逻辑前，先阅读相关脚本，不要只改 `pyproject.toml`。

## Lint Format Typecheck
- 代码格式化：`black src tests`
- 导入排序：`isort src tests`
- 静态检查：`flake8 src tests`
- 类型检查：`mypy src/drama_processor`
- Black 配置来自 `pyproject.toml`：行宽 `88`，目标版本 `py38`。
- isort 配置使用 `profile = "black"`，并保持 `line_length = 88`。
- mypy 已开启较严格约束，包括：
  - `disallow_untyped_defs = true`
  - `disallow_incomplete_defs = true`
  - `check_untyped_defs = true`
  - `disallow_untyped_decorators = true`
  - `no_implicit_optional = true`
  - `strict_equality = true`
- 新代码必须通过这些检查，不要通过弱化类型约束来绕过问题。

## Test Commands
- 默认测试框架是 `pytest`。
- `pyproject.toml` 中的测试目录配置为：`tests`
- 测试文件命名约定：`test_*.py` 或 `*_test.py`
- 测试类命名约定：`Test*`
- 测试函数命名约定：`test_*`
- 运行全量测试：`pytest`
- `pyproject.toml` 已默认附带覆盖率参数：`--cov=drama_processor`、`--cov-report=term-missing`、`--cov-report=html`、`--cov-report=xml`
- 运行单个测试文件：`pytest tests/test_cli.py`
- 运行单个测试函数：`pytest tests/test_cli.py::test_process_command`
- 运行单个测试类中的单个用例：`pytest tests/test_cli.py::TestCLI::test_process_command`
- 使用关键字筛选单测：`pytest tests/test_cli.py -k process`
- 如需只看失败更快定位，可追加：`pytest -x`
- 当前仓库看起来尚未放入完整的 `tests/` 自动化测试集；新增测试时请遵守上述路径与命名规则。

## Common Run Commands
- 使用默认配置运行处理：`drama-processor process /path/to/dramas`
- 指定配置文件：`drama-processor -c configs/default.yaml process /path/to/dramas`
- 只做分析：`drama-processor analyze /path/to/dramas --format json`
- 查看某个子命令帮助：`drama-processor process --help`
- GUI 调试通常从根目录 `run_gui.py` 开始。

## Code Style
- 使用 4 空格缩进，不要混用制表符。
- 默认遵循 Black 格式，不手写与 Black 冲突的排版。
- 导入顺序遵循 isort/Black 风格：标准库、第三方、本地模块分组。
- 包内模块大量使用相对导入，例如 `from ..config import ...`，修改现有文件时保持一致。
- 行宽以 88 为准；超长表达式优先拆行，不要牺牲可读性。

## Types And Data Modeling
- 类型注解是强约束，不是可选项。
- 新增或修改函数时，参数和返回值都应显式标注类型。
- 避免引入隐式 `Optional`；与 mypy 配置保持一致。
- 配置和领域数据优先使用 Pydantic 模型，参考 `src/drama_processor/models/config.py`。
- 模型字段默认通过 `Field(...)` 声明说明、默认值和约束。
- 不要用松散的 `dict[str, Any]` 替代已有模型，除非确有边界层需要。

## Naming Conventions
- 模块名、函数名、变量名使用 `snake_case`。
- 类名使用 `PascalCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- Click 命令参数保持 kebab-case 风格，例如 `--no-interactive`、`--refresh-tail-cache`。
- 配置字段名与 YAML 键名尽量保持一致，避免同义重复命名。

## Logging And Output
- 日志统一走 `src/drama_processor/utils/logging.py` 中的 `setup_logging`。
- 模块内 logger 获取方式保持为：`logging.getLogger(__name__)`。
- 优先输出可执行、可定位的问题信息，不要用无上下文的 `print`。
- CLI 面向用户的错误提示可使用 `click.echo(..., err=True)`。
- 长流程建议沿用现有 `ProgressLogger`、`TimedLogger` 模式，保持日志风格一致。

## Error Handling
- 先校验输入，再执行业务逻辑；CLI 参数错误可直接明确退出。
- 对文件路径、配置、外部命令、网络调用都要做失败分支处理。
- 捕获异常时要么补充上下文后重新抛出，要么记录足够清晰的日志，不要静默吞错。
- 保持现有代码风格中的显式错误消息，例如缺目录、参数范围非法、授权缺失等。

## Config And Secrets
- 默认配置入口是 `configs/default.yaml`。
- 用户级配置放在 `configs/users/`，改动前先确认是否应该改默认配置还是某个用户配置。
- 涉及 Feishu webhook、License、路径等敏感值时，不要把真实秘密写入仓库。
- 优先通过本地配置或环境变量注入敏感信息。
- 修改配置字段时，同步检查对应的 Pydantic 模型、加载器和 CLI 参数。

## External Integrations
- 飞书相关逻辑集中在 `src/drama_processor/integrations/` 与部分配置模型中。
- Lite 版本与 License 控制已经在 README 和 CLI 设计中体现，改动权限或功能开关时要同时核对两套入口。

## Testing Guidance For Agents
- 修改 CLI 层时，优先补 `tests/` 下的命令解析和参数覆盖测试。
- 修改配置加载时，优先覆盖默认值、用户配置合并、缺省字段和非法配置。
- 修改处理编排时，优先隔离文件系统、FFmpeg 调用和网络依赖。
- 如果没有现成自动化测试，至少运行与改动最相关的 lint、mypy 和手动命令验证。

## Change Discipline
- 只改与当前任务直接相关的文件。
- 除非用户要求，不要顺手整理无关格式、重命名无关符号或搬移文件。
- 若发现仓库里有与你任务无关的脏工作区，忽略它，不要回滚。

## Practical References
- 项目元数据与工具配置：`pyproject.toml`
- 默认配置样例：`configs/default.yaml`
- CLI、日志、配置参考：`src/drama_processor/cli/commands.py`、`src/drama_processor/utils/logging.py`、`src/drama_processor/models/config.py`、`src/drama_processor/config/loader.py`

## Final Reminders
- 这个仓库的代理规范以本文件为准。
- 需要新增规则时，优先更新根目录 `AGENTS.md`，不要重新引入分散的 `CLAUDE.md`。
- 输出结果时，说明你改了什么、为什么这样改，以及接下来最值得做的验证或优化。
