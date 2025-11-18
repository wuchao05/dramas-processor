# 飞书轮询剪辑功能

为了避免频繁手动执行 `drama-processor feishu run`，现在可以通过 **飞书轮询任务（watch 模式）** 自动检测待剪辑剧目，并按日期批次触发剪辑脚本。

## 功能特性

- 📡 **定时轮询**：默认每 30 分钟从飞书表格抓取一次“待剪辑”状态。
- 🗂️ **按日期分组**：每个日期视为一个独立批次，可按 `max_dates_per_cycle` 并发触发多个剪辑任务，并自动对“今天/较早日期”赋予更高优先级。
- ⚖️ **智能优先级**：当并发槽位有限且较早日期出现新任务时，会抢占较晚日期的批次，确保当天/较早日期始终优先处理。
- ♻️ **自动追加**：同一天新增的剧会在下一轮循环中自动加入，无需中断现有流程。
- 🔁 **即时同步**：若在飞书中把剧目从 11.18 调整到 11.19，下一轮轮询会以飞书列表为准，未开剪的剧会自动从旧日期剔除并加入新日期。
- ⚙️ **可配置**：轮询周期、同时处理的日期数量、监听的日期范围等均可在 `configs/default.yaml` 调整。
- 🧵 **守护式运行**：可以作为常驻任务运行，也可以通过 `--run-once` 执行单次轮询后退出。

## 配置方式

在 `configs/default.yaml` 中新增（或调整）以下配置：

```yaml
feishu_watcher:
  enabled: true                # 是否启动自动轮询
  poll_interval: 1800          # 轮询间隔（秒）
  max_dates_per_cycle: 1       # 单轮并发触发的日期任务数（>=2 时多日期同步剪辑）
  settle_seconds: 120          # 同一日期任务空闲等待秒数
  settle_rounds: 2             # 连续空轮次数，超过则认为该日期暂时无新剧
  idle_exit_minutes: null      # 无任务时自动退出的分钟数（null 表示一直运行）
  state_dir: "history/feishu_watcher"
  date_whitelist: []           # 仅监听指定日期（如 ["9.17","9.18"]）
  date_blacklist: []           # 忽略的日期
  status_filter: null          # 覆盖默认状态过滤值（默认使用 pending_status_value）
```

> `enabled` 只影响默认行为。就算配置为 `false`，也可以手动执行 `feishu watch` 命令。

## 使用方法

```bash
# 持续轮询飞书，自动剪辑
drama-processor feishu watch

# 修改轮询间隔，只监听指定日期
drama-processor feishu watch --poll-interval 900 --dates "9.17,9.18"

# 仅执行一次轮询后退出
drama-processor feishu watch --run-once
```

命令参数说明：

- `--poll-interval`：覆盖配置中的轮询间隔（秒）。
- `--status`：临时覆盖“待剪辑”状态值。
- `--dates`：只监听逗号分隔的日期（例如 `9.17,9.18`）。
- `--max-dates`：一次轮询中最多自动触发的日期任务数。
- `--run-once`：只执行一次轮询，便于脚本式调用或调试。

## 工作流程

1. 轮询线程调用飞书 API，根据配置筛选状态为“待剪辑”的剧目。
2. 按剧目日期分组，同步提示“9.17 有 X 部待剪辑剧”。
3. 按需要的并发度同时启动若干日期批次（等价于并行执行 `feishu run --date <日期> --yes`），过程中仍会自动更新飞书状态。
4. 剪辑完成后等待一小段时间，若同日期仍有新的待剪辑剧，则继续处理；否则进入下一次轮询。

## 日常建议

- 可以把 `drama-processor feishu watch` 放到 `tmux`/`screen` 中长期运行。
- 若需要不同机器同时监听不同日期，可利用 `--dates` 或 `date_whitelist` 精细控制。
- 建议配合 `enable_feishu_notification`，这样批次开始/完成时会自动通知飞书群。

有了轮询功能，只需保持 watcher 在后台运行，就能 24/7 自动接收飞书新增的待剪辑剧，彻底告别手动重复执行命令的麻烦。祝剪辑顺利！ 🎬
