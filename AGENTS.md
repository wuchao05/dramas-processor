# 代理使用规则
- 始终用中文回复（包括说明、总结和代码注释）。
- 如非明确要求做代码 review，完成代码修改后需自动提交并 push 到远程仓库。

# Repository Guidelines

## Project Structure & Module Organization
- Core package lives in `src/drama_processor/` with `cli/` for Click commands, `core/` for processing pipeline, `models/` for data shapes, `utils/` for helpers, and `config/` for loading defaults.
- Configuration samples stay in `configs/` (default entry is `configs/default.yaml`). Static media (e.g., `assets/tail.mp4`, fonts) sit in `assets/`.
- Usage docs and design notes are in `docs/` and `COMMANDS_USAGE_GUIDE.md`; worked examples are under `examples/`. Legacy helpers are in `scripts/`.
- `test_dramas/` contains manual fixtures for local runs; add automated tests under `tests/` (pyproject points pytest there).

## Setup, Build, Test & Development Commands
- Install runtime deps: `pip install -r requirements.txt`; for full tooling: `pip install -e ".[dev]"`.
- Run the CLI: `drama-processor --help`, `drama-processor process /path/to/dramas`, `drama-processor analyze /path --format json`. Use `-c configs/default.yaml` to pin config.
- Format/lint/type-check: `black src tests`, `isort src tests`, `flake8 src tests`, `mypy src/drama_processor`.
- Tests: `pytest` (pyproject adds coverage: `--cov=drama_processor --cov-report=term-missing`). Prefer targeted flags like `pytest tests/test_cli.py -k process`.

## Coding Style & Naming Conventions
- Python 3.8+; 4-space indentation; Black line length 88 with isort `profile=black`. Keep imports grouped stdlib/third-party/local.
- Type hints are expected; mypy runs in strict-ish mode (e.g., `disallow_untyped_defs=true`).
- Naming: modules and functions use `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`. CLI options should stay kebab-case to match Click usage.
- Logging: route through `utils.logging.setup_logging`; prefer structured, actionable messages over prints.

## Testing Guidelines
- Framework: pytest with coverage; test files should follow `test_*.py` or `*_test.py` under `tests/`.
- Mock external services (Feishu webhooks, filesystem writes) and isolate ffmpeg-heavy paths; for end-to-end smoke, reuse assets from `test_dramas/` but gate behind markers to keep default runs fast.
- Aim for validation of CLI argument parsing, config loading, and processing orchestration; include edge cases around missing assets/configs.

## Commit & Pull Request Guidelines
- Commit messages trend short; prefer `feat:`, `fix:`, `chore:`, `docs:` prefixes in present tense (e.g., `feat: add tail cache refresh`). Keep them focused on one logical change.
- PRs should state the problem, the approach, and user-visible outcomes; include minimal repro/running commands (e.g., `drama-processor process ...`) and note any config defaults touched.
- Update docs/examples when behavior or flags change, and attach before/after output or logs when relevant.

## Configuration & Ops Notes
- Default configuration is loaded from `configs/default.yaml`; override via `-c` or `--config`. Keep secrets (e.g., Feishu webhooks) out of the repo and pass via env or local YAML ignored by git.
- Assets (tail clips, fonts) live in `assets/`; adjust paths in config rather than hardcoding.
- Long-running processing benefits from `--jobs` tuning and `--keep-temp` for debugging; clean up temp dirs if retained.
