"""拉取麦当劳 MCP 数据并缓存到 data/ 目录

用法:
    MCD_TOKEN=xxx python3 scripts/fetch_data.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcd_client import MCDClient  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STORE_CODE = os.getenv("MCD_STORE_CODE", "1400359")  # 默认：麦当劳广州天源路餐厅


def save(name: str, obj) -> None:
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {name} ({os.path.getsize(path)} 字节)")


def main():
    token = os.getenv("MCD_TOKEN")
    if not token:
        print("错误：请先设置环境变量 MCD_TOKEN")
        sys.exit(1)
    c = MCDClient(token)

    print("拉取数据...")

    # 1. 营养数据
    nut = c.call("list-nutrition-foods", {})
    save("nutrition.json", nut)

    # 2. 菜单
    meals = c.call("query-meals", {"storeCode": STORE_CODE, "orderType": 1, "beType": 1})
    save("meals.json", meals)

    # 3. 历史订单
    orders = c.call("order-list", {})
    save("orders.json", orders)

    # 4. 我的券（返回 markdown 文本，直接存原文）
    coupons_text = c.call_text("query-my-coupons", {})
    with open(os.path.join(DATA_DIR, "coupons.md"), "w", encoding="utf-8") as f:
        f.write(coupons_text)
    print(f"  ✓ coupons.md ({len(coupons_text)} 字符)")

    # 5. 积分
    account = c.call("query-my-account", {})
    save("account.json", account)

    # 6. 活动日历（返回 markdown 文本）
    campaign_text = c.call_text("campaign-calendar", {})
    with open(os.path.join(DATA_DIR, "campaign.md"), "w", encoding="utf-8") as f:
        f.write(campaign_text)
    print(f"  ✓ campaign.md ({len(campaign_text)} 字符)")

    print("全部完成。数据已缓存到 data/")


if __name__ == "__main__":
    main()
