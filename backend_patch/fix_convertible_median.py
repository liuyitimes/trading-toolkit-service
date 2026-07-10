#!/usr/bin/env python3
"""
修复可转债中位数计算 BUG（v5 - 最终方案）
问题: EM 数据中部分转债的 conversion_value 错误（报低），导致 premium_rate 虚高
      v3: cv>=50, price<=500 → valid_count=52, premium_median=88.59（p25=2.86, p75=146.66）
      p25=2.86 说明 25% 的转债溢价率正常（< 2.86%），但中位数被高溢价转债拉高
修复:
  - cv >= 50（v3 方案，正常转股价值下限）
  - price 90-500（过滤异常价格）
  - premium_rate -50% 到 100%（正常转债溢价率范围，过滤 cv 错误导致的虚高 premium）
  - price_min/max/median 从 valid 计算（一致性）
"""
from pathlib import Path

BACKEND_FILE = r"d:\Develop\GitHub\trading-toolkit-service\cloudrun\services\convertible_bond.py"

def apply_patch():
    f = Path(BACKEND_FILE)
    if not f.exists():
        print(f"[ERROR] 后端文件不存在: {BACKEND_FILE}")
        return False

    content = f.read_text(encoding="utf-8")
    original = content

    # 修复 valid 过滤
    old_block = """        # 过滤无效数据，避免异常值污染中位数：
        # - premium_rate=0：无转股数据
        # - conversion_value<30：EM 数据异常（正常转股价值 30-300）
        # - price>300 或 price<90：异常价格转债（退市债、妖债）
        valid = df[(df['premium_rate'] != 0) & (df['conversion_value'] >= 30) & (df['price'] <= 300) & (df['price'] >= 90)]
        if valid.empty:
            return None

        # 使用 5%-95% 分位数过滤异常值（稳健统计方法）
        p5 = valid['premium_rate'].quantile(0.05)
        p95 = valid['premium_rate'].quantile(0.95)
        robust = valid[(valid['premium_rate'] >= p5) & (valid['premium_rate'] <= p95)]

        price_median = float(robust['price'].median())
        premium_median = float(robust['premium_rate'].median())
        double_low_median = float(robust['double_low'].median())"""

    new_block = """        # 过滤无效数据，避免异常值污染中位数：
        # - premium_rate=0：无转股数据
        # - conversion_value<50：EM 数据异常（正常转股价值 50-300，低于 50 说明数据错误）
        # - price>500 或 price<90：异常价格转债（退市债、妖债）
        # - premium_rate>100 或 <-50：异常溢价率（cv 数据错误导致的虚高 premium）
        valid = df[
            (df['premium_rate'] != 0) &
            (df['conversion_value'] >= 50) &
            (df['price'] <= 500) &
            (df['price'] >= 90) &
            (df['premium_rate'] >= -50) &
            (df['premium_rate'] <= 100)
        ]
        if valid.empty:
            return None

        price_median = float(valid['price'].median())
        premium_median = float(valid['premium_rate'].median())
        double_low_median = float(valid['double_low'].median())"""

    if old_block in content:
        content = content.replace(old_block, new_block)
        print("[OK] 修复 valid 过滤（cv>=50, 90<=price<=500, -50<=premium<=100）")
    else:
        print("[WARN] 未找到 v4 的 valid 过滤块，尝试匹配其他版本...")
        # 尝试 v3
        old_v3 = """        # 过滤无效数据，避免异常值污染中位数：
        # - premium_rate=0：无转股数据
        # - conversion_value<50：EM 数据异常（正常转股价值 50-300，低于 50 说明数据错误或"妖债"）
        # - price>500：异常高价转债（如退市债、妖债），不代表市场整体温度
        valid = df[(df['premium_rate'] != 0) & (df['conversion_value'] >= 50) & (df['price'] <= 500)]
        if valid.empty:
            return None

        price_median = float(valid['price'].median())
        premium_median = float(valid['premium_rate'].median())
        double_low_median = float(valid['double_low'].median())"""

        new_v3 = new_block  # 同样的替换

        if old_v3 in content:
            content = content.replace(old_v3, new_v3)
            print("[OK] 修复 valid 过滤（v3→v5）")
        else:
            print("[ERROR] 未找到任何匹配的 valid 过滤块")

    if content != original:
        f.write_text(content, encoding="utf-8")
        print(f"\n[SUCCESS] 补丁已应用到: {BACKEND_FILE}")
        return True
    else:
        print("\n[INFO] 无变更")
        return False


if __name__ == "__main__":
    apply_patch()
