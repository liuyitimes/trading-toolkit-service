# LOF 溢价观测 systemd 定时器示例

`lof-premium-capture.timer` 在交易日 20:30（中国标准时间）触发
`lof-premium-capture.service`，执行 `cli.py capture`。当日已公布单位净值晚于
20:30 可用时，任务保持缺口并在次日重试窗口内补齐；任务行与数据库锁保证
同类任务不会并发运行。

`lof-premium-backfill.service` 是一次性回补单元（`systemctl start` 时通过
模板参数传入年份，例如 `systemctl start lof-premium-backfill@2026.service`）。

安装步骤：

1. 将模板中的 `__CLOUDRUN_DIR__`、`__PYTHON__`、`__SERVICE_USER__` 替换为实际值。
2. 复制到 `~/.config/systemd/user/` 或 `/etc/systemd/system/`。
3. 启用并启动定时器：

   ```bash
   systemctl --user enable lof-premium-capture.timer
   systemctl --user start lof-premium-capture.timer
   ```

首次启用前先导入交易日历并执行一次当前年度回补：

```bash
cd __CLOUDRUN_DIR__
python cli.py calendar-import --year 2026
python cli.py backfill --year 2026
```

外部调度器只负责按窗口调用命令；调度本身不承载领域状态。
