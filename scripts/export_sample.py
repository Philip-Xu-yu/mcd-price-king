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
        profiles.append({
            "name": p["name"],
            "price": p["price"],
            "original": p["original"],
            "save": p["save"],
            "kcal": p["kcal"],
            "protein": p["protein"],
            "sodium": p["sodium"],
            "image": p["image"],
            "items": [{"name": it["name"], "price": it["price"]} for it in p["items"]],
        })
        print(f"  {p['name']} ¥{p['price']} 省{p['save']}")

    js = "/* 示例数据快照：来自麦当劳官方 MCP 的真实请求结果，非实时 */\n"
    js += "window.MC_SAMPLE = " + json.dumps(profiles, ensure_ascii=False, indent=1) + ";\n"
    with open(os.path.join(DOCS, "data.js"), "w", encoding="utf-8") as f:
        f.write(js)
    print(f"\n完成：{len(profiles)} 个套餐写入 docs/data.js")


if __name__ == "__main__":
    main()
