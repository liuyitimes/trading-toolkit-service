# LOF 溢价观测外部调度

服务不在 Flask 进程内启动定时线程。将 `lof-premium-capture.service` 和 `lof-premium-capture.timer` 安装到 `/etc/systemd/system/` 后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lof-premium-capture.timer
systemctl list-timers lof-premium-capture.timer
```

定时器从中国标准时间 20:30 起每 30 分钟调用一次。采集命令会自行拒绝非交易日和窗口外运行，并通过 PostgreSQL 任务锁防止并发。生产环境应在 `/etc/trading-toolkit/service.env` 配置 `DATABASE_URL`。

导入经沪深交易所官方年度休市安排核验的 JSON 日历：

```bash
flask --app app lof-trading-calendar-import --file /srv/calendar/2026.json --source 上交所和深交所年度休市安排 --version 2026
flask --app app lof-premium-backfill --year 2026
```

日历 JSON 是对象时使用 `trading_days` 数组，否则直接使用日期数组；日期格式为 `YYYY-MM-DD`。不应以周末规则或通用节假日库替代官方日历。
