"""生成静态试算页的数据快照 docs/data.js

用法: MCD_TOKEN=xxx python scripts/export_sample.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent  # noqa: E402
from data_utils import parse_meals  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def verify_listed_save(profile):
    """仅核对列出单品价格的完整性与算术，不证明商品组成真实。"""
    items = profile.get("items", [])
    listed_sum = round(sum(float(it.get("price") or 0) for it in items), 1)
    has_complete_prices = bool(items) and all(float(it.get("price") or 0) > 0 for it in items)
    computed_save = round(listed_sum - float(profile["price"]), 1)
    source_save = profile.get("save")
    save_verified = (has_complete_prices and isinstance(source_save, (int, float))
                     and abs(computed_save - float(source_save)) <= 0.1)
    return listed_sum, computed_save, save_verified


def main():
    os.makedirs(DOCS, exist_ok=True)
    meals = parse_meals()
    combos = [(c, v) for c, v in meals.items() if v["original_price"] > v["price"]]
    combos.sort(key=lambda x: -(x[1]["original_price"] - x[1]["price"]))

    profiles = []
    for code, info in combos[:24]:
        try:
            p = agent._meal_profile(None, info["name"], None)
        except Exception:
            continue
        if not p:
            continue
        listed_sum, computed_save, save_verified = verify_listed_save(p)
        profiles.append({
            "name": p["name"],
            "price": p["price"],
            "original": p["original"],
            "save": computed_save if save_verified else None,
            "save_verified": save_verified,
            "listed_sum": listed_sum,
            "kcal": p["kcal"],
            "protein": p["protein"],
            "sodium": p["sodium"],
            "image": p["image"],
            "items": [{"name": it["name"], "price": it["price"]} for it in p["items"]],
        })
        label = f"拆单差额 ¥{computed_save}" if save_verified else "拆单差额待核实"
        print(f"  {p['name']} ¥{p['price']} {label}")

    js = "/* 示例数据快照：来自麦当劳官方 MCP 的真实请求结果，非实时 */\n"
    js += "window.MC_SAMPLE = " + json.dumps(profiles, ensure_ascii=False, indent=1) + ";\n"
    with open(os.path.join(DOCS, "data.js"), "w", encoding="utf-8") as f:
        f.write(js)
    print(f"\n完成：{len(profiles)} 个套餐写入 docs/data.js")


if __name__ == "__main__":
    main()
