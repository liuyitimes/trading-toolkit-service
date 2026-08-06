## 目标

让服务端成为可转债历史价格和收益口径的唯一计算方，前端只消费事实和做展示格式化。

## 决策

1. 继续使用现有东方财富日 K 线接口，新增通用 K 线解析函数，按证券代码自动生成沪深 `secid`。
2. 股权登记日收盘价字段命名为 `registration_close_price`。登记日后收尾价字段命名为 `post_registration_close_price`，表示股权登记日之后的第一个可验证 A 股交易日收盘价。
3. 参与配债后总收益按“一手可转债面值 1,000 元”口径计算：`stock_leg_profit + bond_expected_profit`。其中 `stock_leg_profit = (post_registration_close_price - registration_close_price) * actual_shares_for_1_lot`，`bond_expected_profit = 1000 * placement_premium_rate / 100`。
4. 今年上市新债接口命名为 `GET /api/v1/convertible/new-listed`，默认返回中国时区当前自然年上市的新债。涨幅字段均返回数值百分比，缺失时为 `null`。
5. 上市以来涨幅以上市日收盘价为基准；本月涨幅以本月第一个可验证交易日收盘价为基准；上市前三日涨幅以面值 100 元为基准，取上市后第 1、2、3 个交易日中当前可获得的最新收盘价或上市当日实时价，第三个交易日收盘后冻结为第三日收盘价。

## 非目标

- 不引入数据库迁移或新的持久化历史价格表。
- 不承诺登记日后实际卖出价格、个人成交价、税费或资金占用成本。
- 不改变待配债观察范围和已过期排序规则。
