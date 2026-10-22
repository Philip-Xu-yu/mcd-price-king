"""数据解析工具：把 MCP 原始返回解析成简单结构"""
import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_json(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def parse_nutrition() -> list:
    """解析营养表 → [{name, kcal, protein, fat, carb, sodium, calcium}]"""
    raw = load_json("nutrition.json")
    data = raw.get("data", "")
    if not isinstance(data, str):
        return []
    # 格式: "[160]{productName,...}:\n  名称,null,...\n..."
    m = re.search(r"\[(\d+)\]\{([^}]+)\}:\n(.*)", data, re.S)
    if not m:
        m = re.search(r"\[(\d+)\]\{([^}]+)\}:\\n(.*)", data, re.S)
    if not m:
        return []
    body = m.group(3)
    rows = []
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) < 9:
            continue
        try:
            rows.append({
                "name": p[0],
                "kcal": float(p[3]),
                "protein": float(p[4]),
                "fat": float(p[5]),
                "carb": float(p[6]),
                "sodium": float(p[7]),
                "calcium": float(p[8]),
            })
        except (ValueError, IndexError):
            continue
    return rows


def parse_meals() -> dict:
    """解析菜单 → {code: {name, price, original_price, category}}"""
    raw = load_json("meals.json")
    data = raw.get("data", {})
    meals = data.get("meals", {})
    cat_map = {}
    for c in data.get("categories", []):
        for m in c.get("meals", []):
            cat_map[m.get("code")] = c.get("name")
    out = {}
    for code, v in meals.items():
        try:
            price = float(v.get("currentPrice", 0) or 0)
            orig = float(v.get("originalPrice", 0) or 0)
        except (ValueError, TypeError):
            price, orig = 0, 0
        out[code] = {
            "name": v.get("name", ""),
            "price": price,
            "original_price": orig,
            "category": cat_map.get(code, ""),
            "image": v.get("image", ""),
        }
    return out


def parse_orders() -> list:
    """解析历史订单 → [{id, time, store, amount, items:[(name, qty)]}]"""
    raw = load_json("orders.json")
    data = raw.get("data", {})
    orders = data.get("list", []) or []
    out = []
    for o in orders:
        items = []
        for p in o.get("orderProductList", []):
            items.append((p.get("productName", ""), p.get("quantity", 1)))
        out.append({
            "id": o.get("orderId"),
            "time": o.get("createTime"),
            "store": o.get("storeName"),
            "amount": float(o.get("realTotalAmount", 0) or 0),
            "items": items,
        })
    return out


def parse_account() -> dict:
    raw = load_json("account.json")
    return raw.get("data", {})


if __name__ == "__main__":
    nut = parse_nutrition()
    meals = parse_meals()
    orders = parse_orders()
    acct = parse_account()
    print(f"营养条目: {len(nut)}")
    print(f"菜单条目: {len(meals)}")
    print(f"历史订单: {len(orders)}")
    print(f"积分: 可用{acct.get('availablePoint')} 已过期{acct.get('expiredPoint')} 累计{acct.get('accumulativePoint')}")
    print("\n订单明细:")
    for o in orders:
        print(f"  {o['time']} {o['store']} ¥{o['amount']} {o['items']}")
