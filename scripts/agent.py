"""agent.py - 把四个功能统一为「一个输入 → 一个结构化答案」

每个函数返回 dict，由 UI 层渲染成卡片。
"""
import os

from mcd_client import MCDClient
from data_utils import parse_meals, parse_orders

STORE_CODE = os.getenv("MCD_STORE_CODE", "1400359")


def _client(token=None):
    return MCDClient(token)


def check(token, name, store_code=None, meals=None):
    """单品鉴定 → dict；优先使用当前门店菜单，避免缓存价冒充实时价。"""
    sc = store_code or STORE_CODE
    meals = meals if meals is not None else parse_meals()
    hits = [(c, v) for c, v in meals.items() if v["name"] == name.strip()]
    hits.sort(key=lambda x: -(x[1]["original_price"] - x[1]["price"]))
    if not hits:
        return {"type": "check", "found": False, "query": name}

    code, info = hits[0]
    c = _client(token)
    d = c.call("query-meal-detail", {"storeCode": sc, "orderType": 1, "beType": 1, "code": code})
    detail = d.get("data", {})
    items = []
    for r in detail.get("rounds", []):
        for ch in r.get("choices", []):
            if ch.get("isDefault") == 1:
                items.append(ch.get("name", ""))

    rows = []
    single_sum = 0.0
    for it in items:
        p = 0.0
        # 1) 精确匹配
        for c2, v2 in meals.items():
            if v2["name"] == it:
                p = v2["price"]
                break
        # 2) 模糊匹配，但排除带"套/餐/盒"的套餐类商品
        if not p:
            for c2, v2 in meals.items():
                n2 = v2["name"]
                if any(k in n2 for k in ["套", "餐", "盒", "桶"]):
                    continue
                if it in n2 or n2 in it:
                    p = v2["price"]
                    break
        single_sum += p
        rows.append({"name": it, "price": p})

    verified = all(row["price"] > 0 for row in rows) and bool(rows)
    computed_save = round(single_sum - info["price"], 1) if verified else None
    return {
        "type": "check",
        "found": True,
        "code": code,
        "name": info["name"],
        "image": detail.get("image", ""),
        "price": info["price"],
        "original": info["original_price"],
        "category": info["category"],
        "items": rows,
        "single_sum": round(single_sum, 1),
        "save": computed_save,
        "save_verified": verified,
        "strike_fake": verified and info["original_price"] > single_sum,
        "is_combo": bool(items),
    }


def oneplus(token):
    """1+1 破解 → dict"""
    meals = parse_meals()
    combo_code = combo_price = combo_name = None
    for c, v in meals.items():
        if "随心配" in v["name"]:
            combo_code, combo_price, combo_name = c, v["price"], v["name"]
            break
    if not combo_code:
        return {"type": "oneplus", "found": False}

    c = _client(token)
    d = c.call("query-meal-detail", {"storeCode": STORE_CODE, "orderType": 1, "beType": 1, "code": combo_code})
    rounds = d.get("data", {}).get("rounds", [])
    zones = [[ch.get("name", "") for ch in r.get("choices", []) if ch.get("name")] for r in rounds]
    if len(zones) < 2:
        return {"type": "oneplus", "found": False}

    def sp(n):
        for c2, v2 in meals.items():
            if v2["name"] == n or n in v2["name"] or v2["name"] in n:
                return v2["price"]
        return 0.0

    results = []
    for a in zones[0]:
        for b in zones[1]:
            results.append({
                "a": a, "ap": sp(a), "b": b, "bp": sp(b),
                "value": round(sp(a) + sp(b), 1),
            })
    results.sort(key=lambda x: -x["value"])
    return {
        "type": "oneplus",
        "found": True,
        "name": combo_name,
        "price": combo_price,
        "best": results[:3],
        "worst": results[-3:],
        "gap": round(results[0]["value"] - results[-1]["value"], 1),
    }


def review(token):
    """订单复盘 → dict"""
    orders = parse_orders()
    if not orders:
        return {"type": "review", "found": False}
    total = sum(o["amount"] for o in orders if o["amount"] > 0)
    return {
        "type": "review",
        "found": True,
        "total": round(total, 1),
        "count": len(orders),
        "orders": [{
            "time": o["time"],
            "store": o["store"],
            "amount": o["amount"],
            "items": ", ".join(f"{n}×{q}" for n, q in o["items"]),
        } for o in orders],
    }


def find_stores(token, city="", keyword=""):
    """按城市/关键词搜门店 → [{code, name, address, distance, open, close, reservation}]"""
    c = _client(token)
    try:
        d = c.call("query-nearby-stores", {
            "beType": 1, "searchType": 2, "city": city, "keyword": keyword,
        })
    except Exception:
        return []
    out = []
    for s in d.get("data", []):
        out.append({
            "code": s.get("storeCode"),
            "name": s.get("storeName"),
            "address": s.get("address"),
            "distance": s.get("distance"),
            "open": s.get("businessStartTime"),
            "close": s.get("businessEndTime"),
            "reservation": s.get("reservation"),
        })
    return out


def get_menu(token, store_code=None):
    """拉指定门店的菜单 → {code: {name, price, original_price, category, image}}"""
    sc = store_code or STORE_CODE
    c = _client(token)
    d = c.call("query-meals", {"storeCode": sc, "orderType": 1, "beType": 1})
    data = d.get("data", {})
    cat_map = {}
    for cat in data.get("categories", []):
        for m in cat.get("meals", []):
            cat_map[m.get("code")] = cat.get("name", "").replace("\n", "")
    meals = {}
    for code, v in data.get("meals", {}).items():
        try:
            price = float(v.get("currentPrice", 0) or 0)
            orig = float(v.get("originalPrice", 0) or 0)
        except (ValueError, TypeError):
            price, orig = 0, 0
        meals[code] = {
            "name": v.get("name", ""),
            "price": price,
            "original_price": orig,
            "category": cat_map.get(code, ""),
            "image": v.get("image", ""),
        }
    return meals


def best_deal(token, product_code, store_code=None):
    """找适用该商品的券并算价 → 最优买法"""
    sc = store_code or STORE_CODE
    c = _client(token)
    coupons = c.call("query-store-coupons", {
        "storeCode": sc, "orderType": 1, "beType": 1,
    }).get("data", [])
    deals = []
    for cp in coupons:
        for p in cp.get("products", []):
            if p.get("productCode") == product_code:
                try:
                    r = c.call("calculate-price", {
                        "storeCode": sc, "orderType": 1, "beType": 1,
                        "items": [{
                            "productCode": product_code, "quantity": 1,
                            "couponId": cp.get("couponId"),
                            "couponCode": cp.get("couponCode"),
                        }],
                    }).get("data", {})
                except Exception:
                    r = None
                if r:
                    deals.append({
                        "coupon": cp.get("title"),
                        "price": r.get("price", 0) / 100,
                        "original": r.get("productOriginalPrice", 0) / 100,
                        "discount": r.get("discount", 0) / 100,
                        "expire": (cp.get("tradeDateTime") or "").split(" ")[-1],
                    })
    deals.sort(key=lambda x: x["price"])
    return deals


def claim_all_coupons(token):
    """一键领取麦麦省所有可领券 → 返回领取结果"""
    c = _client(token)
    d = c.call("auto-bind-coupons", {})
    data = d.get("data", {})
    return {
        "success": [x.get("couponName") for x in data.get("successCoupons", [])],
        "failed": [x.get("couponName") for x in data.get("failedCoupons", [])],
    }


def _nutrition_of(items):
    """套餐组成项 → 营养求和 {kcal, protein, sodium}"""
    from data_utils import parse_nutrition
    nut = parse_nutrition()
    total = {"kcal": 0.0, "protein": 0.0, "sodium": 0.0}
    for it in items:
        for n in nut:
            if n["name"] == it or it in n["name"] or n["name"] in it:
                total["kcal"] += n["kcal"]
                total["protein"] += n["protein"]
                total["sodium"] += n["sodium"]
                break
    return total


def _meal_profile(token, name, store_code, meals=None):
    """套餐完整画像：价格 + 组成 + 营养 + 优惠评分"""
    d = check(token, name, store_code, meals=meals)
    if not d.get("found"):
        return None
    nut = _nutrition_of([it["name"] for it in d.get("items", [])])
    score = 10
    if d.get("strike_fake"):
        score += 50
    if d.get("original", 0) > 0:
        rate = (d["original"] - d["price"]) / d["original"]
        if rate >= 0.4:
            score += 30
        elif rate >= 0.25:
            score += 15
    if d.get("save", 0) is not None and d["save"] < 0:
        score += 20
    return {
        "code": d.get("code"),
        "name": d["name"],
        "price": d["price"],
        "original": d["original"],
        "save": d["save"],
        "save_verified": d.get("save_verified", False),
        "items": d["items"],
        "strike_fake": d["strike_fake"],
        "trick_score": min(score, 100),
        "image": d.get("image", ""),
        "kcal": round(nut["kcal"], 1),
        "protein": round(nut["protein"], 1),
        "sodium": round(nut["sodium"], 1),
    }


def _metric_foods(menu):
    """麦当劳度量衡：薯条/麦乐鸡/派 的价格和营养（从菜单动态取，取不到用默认）"""
    refs = {
        "small_fries": {"name": "小薯条", "price": 13.5, "kcal": 210, "protein": 3},
        "mcnuggets": {"name": "麦乐鸡5块", "price": 14.0, "kcal": 213, "protein": 12},
        "pie": {"name": "香芋派", "price": 8.0, "kcal": 232, "protein": 2},
    }
    for key, ref in refs.items():
        for code, v in menu.items():
            if ref["name"] in v["name"] or v["name"] in ref["name"]:
                ref["price"] = v["price"]
                break
    return refs


def recommend_budget(menu, budget, preference="省钱", limit=3):
    """按单份套餐菜单展示价筛选；未知的拆单/营养数据不参与伪排序。"""
    if budget <= 0 or limit < 1:
        return []
    candidates = [dict(code=code, **v) for code, v in menu.items()
                  if v.get("name") and 0 < v.get("price", 0) <= budget
                  and v.get("original_price", 0) > v.get("price", 0)]
    if preference == "折扣":
        candidates.sort(key=lambda v: (-(v["original_price"] - v["price"]), v["price"], v["name"]))
    elif preference in ("蛋白质", "热量低"):
        metric = "protein" if preference == "蛋白质" else "kcal"
        known = [v for v in candidates if isinstance(v.get(metric), (int, float))
                 and v.get(metric) is not None]
        if not known:
            return []
        candidates = known
        if preference == "蛋白质":
            candidates.sort(key=lambda v: (-float(v[metric]), v["price"], v["name"]))
        else:
            candidates.sort(key=lambda v: (float(v[metric]), v["price"], v["name"]))
    elif preference == "拆单差额":
        known = [v for v in candidates if v.get("save_verified") is True
                 and isinstance(v.get("save"), (int, float))]
        if not known:
            return []
        candidates = known
        candidates.sort(key=lambda v: (-float(v["save"]), v["price"], v["name"]))
    else:
        candidates.sort(key=lambda v: (v["price"], -(v["original_price"] - v["price"]), v["name"]))
    return candidates[:limit]


def compare(token, name_a, name_b, store_code=None, menu=None):
    """两个套餐比价 → dict；传入门店菜单时使用同一门店的价格和编码。"""
    sc = store_code or STORE_CODE
    menu = menu if menu is not None else (get_menu(token, sc) if store_code else parse_meals())
    a = _meal_profile(token, name_a, sc, meals=menu)
    b = _meal_profile(token, name_b, sc, meals=menu)
    if not a and not b:
        return {"type": "compare", "found": False, "a": name_a, "b": name_b}
    if not a:
        return {"type": "compare", "found": False, "a": name_a, "b": name_b,
                "reason": f"没找到「{name_a}」"}
    if not b:
        return {"type": "compare", "found": False, "a": name_a, "b": name_b,
                "reason": f"没找到「{name_b}」"}

    refs = _metric_foods(menu)

    # 券自动匹配：套餐本身 + 组成项的适用券
    try:
        a["deals"] = best_deal(token, a.get("code"), sc)
        if not a["deals"]:
            a["deals"] = combo_deals(token, a, sc)
        b["deals"] = best_deal(token, b.get("code"), sc)
        if not b["deals"]:
            b["deals"] = combo_deals(token, b, sc)
    except Exception:
        a["deals"], b["deals"] = [], []

    # 差价
    diff = round(a["price"] - b["price"], 1)
    if diff < 0:
        cheaper, pricier, saving = "a", "b", abs(diff)
    elif diff > 0:
        cheaper, pricier, saving = "b", "a", abs(diff)
    else:
        cheaper, pricier, saving = "tie", "tie", 0.0

    # 麦当劳度量衡：省钱换算
    food_txt = ""
    if saving >= 1:
        picks = [(refs["mcnuggets"], "5块麦乐鸡"), (refs["small_fries"], "小薯条"),
                 (refs["pie"], "香芋派")]
        best_n, best_ref = 0, None
        for ref, label in picks:
            n = int(saving // max(ref["price"], 1))
            if n >= 1 and ref["price"] * n > best_n * (best_ref["price"] if best_ref else 1):
                best_n, best_ref = n, ref
        if best_ref:
            food_txt = f"≈ <b>{best_n}</b> 份「{best_ref['name']}」"
        else:
            food_txt = f"不到一份「{refs['pie']['name']}」"
    elif saving > 0:
        food_txt = f"不到一份「{refs['pie']['name']}」"

    # 蛋白换算
    p_a = a["protein"]
    p_b = b["protein"]
    p_win = "a" if p_a > p_b else ("b" if p_b > p_a else "tie")
    protein_food = ""
    if p_win != "tie":
        pdiff = abs(p_a - p_b)
        n = pdiff / refs["mcnuggets"]["protein"]
        protein_food = f"≈ <b>{n:.1f}</b> 份麦乐鸡(5块)的蛋白"

    # 结论
    win_reasons = []
    if cheaper == "a":
        win_reasons.append(f"A 更省钱（省 ¥{saving}）")
    elif cheaper == "b":
        win_reasons.append(f"B 更省钱（省 ¥{saving}）")
    else:
        win_reasons.append("两款价格相同")
    if p_win == "a":
        win_reasons.append(f"A 蛋白更多（{p_a}g vs {p_b}g）")
    elif p_win == "b":
        win_reasons.append(f"B 蛋白更多（{p_b}g vs {p_a}g）")
    if a["kcal"] < b["kcal"]:
        win_reasons.append(f"A 热量更低（{a['kcal']} vs {b['kcal']} kcal）")
    elif b["kcal"] < a["kcal"]:
        win_reasons.append(f"B 热量更低（{b['kcal']} vs {a['kcal']} kcal）")

    if len(win_reasons) == 1:
        verdict = f"闭眼选 {'A' if win_reasons[0].startswith('A') else 'B'} —— {win_reasons[0]}"
    else:
        verdict = "平手局，看你要什么：" + "；".join(win_reasons)

    return {
        "type": "compare",
        "found": True,
        "a": a,
        "b": b,
        "diff": diff,
        "saving": saving,
        "cheaper": cheaper,
        "food_txt": food_txt,
        "protein_food": protein_food,
        "verdict": verdict,
    }


def combo_deals(token, profile, store_code=None):
    """查套餐组成项适用的券（券适用于套餐内单品的情况）"""
    sc = store_code or STORE_CODE
    c = _client(token)
    try:
        coupons = c.call("query-store-coupons", {
            "storeCode": sc, "orderType": 1, "beType": 1,
        }).get("data", [])
    except Exception:
        return []
    item_names = [it["name"] for it in profile.get("items", [])]
    out = []
    seen = set()
    for cp in coupons:
        for p in cp.get("products", []):
            pname = p.get("productName", "")
            for it in item_names:
                if (pname and it) and (pname in it or it in pname):
                    key = cp.get("couponId")
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        r = c.call("calculate-price", {
                            "storeCode": sc, "orderType": 1, "beType": 1,
                            "items": [{
                                "productCode": p.get("productCode"), "quantity": 1,
                                "couponId": cp.get("couponId"),
                                "couponCode": cp.get("couponCode"),
                            }],
                        }).get("data", {})
                    except Exception:
                        r = None
                    if r:
                        out.append({
                            "coupon": cp.get("title"),
                            "price": r.get("price", 0) / 100,
                            "original": r.get("productOriginalPrice", 0) / 100,
                            "discount": r.get("discount", 0) / 100,
                            "expire": (cp.get("tradeDateTime") or "").split(" ")[-1],
                            "for_item": it,
                        })
                    break
            else:
                continue
            break
    return out


def create_combo_order(token, store_code, meal_code, quantity=1):
    """真实创建麦当劳订单（到店外带）。返回 {orderId, payH5Url, detail, takeWay}"""
    sc = store_code or STORE_CODE
    c = _client(token)
    # 1) 先算价，从返回里拿取餐方式列表（create-order 要求 takeWayCode 从这里选）
    price = c.call("calculate-price", {
        "storeCode": sc, "orderType": 1, "beType": 1,
        "items": [{"productCode": meal_code, "quantity": quantity}],
    }).get("data", {})
    ways = price.get("takeWayList") or []
    codes = [w.get("code") for w in ways if w.get("code")]
    take = "take-in-store" if "take-in-store" in codes else (codes[0] if codes else "take-in-store")
    # 2) 创建订单
    r = c.call("create-order", {
        "storeCode": sc, "orderType": 1, "beType": 1, "takeWayCode": take,
        "items": [{"productCode": meal_code, "quantity": quantity}],
    }).get("data", {})
    return {
        "orderId": r.get("orderId"),
        "payH5Url": r.get("payH5Url"),
        "detail": r.get("orderDetail") or {},
        "takeWay": take,
    }


def cancel_combo_order(token, order_id, reason="3"):
    """取消已创建订单。返回 {success, orderId}"""
    c = _client(token)
    r = c.call("cancel-order", {
        "orderId": order_id, "cancelReasonCode": reason,
    }).get("data", {})
    return {"success": bool(r.get("cancelResult")), "orderId": order_id}


def guard(token):
    """资产管家 → dict"""
    c = _client(token)
    acct = c.call("query-my-account", {}).get("data", {})
    avail = float(acct.get("availablePoint") or 0)
    expired = float(acct.get("expiredPoint") or 0)

    coupons = []
    raw = c.call("query-store-coupons", {"storeCode": STORE_CODE, "orderType": 1, "beType": 1}).get("data", [])
    for cp in raw:
        r = None
        prods = cp.get("products", [])
        if prods:
            try:
                r = c.call("calculate-price", {
                    "storeCode": STORE_CODE, "orderType": 1, "beType": 1,
                    "items": [{"productCode": prods[0].get("productCode"), "quantity": 1,
                               "couponId": cp.get("couponId"), "couponCode": cp.get("couponCode")}],
                }).get("data", {})
            except Exception:
                r = None
        entry = {
            "title": cp.get("title", ""),
            "expire": (cp.get("tradeDateTime") or "").split(" ")[-1],
            "product": prods[0].get("productName", "") if prods else "",
        }
        if r:
            entry["price"] = r.get("price", 0) / 100
            entry["original"] = r.get("productOriginalPrice", 0) / 100
            entry["discount"] = r.get("discount", 0) / 100
        coupons.append(entry)

    mall_rows = []
    mall = c.call("mall-points-products", {"catRuleIds": "1>4,2"}).get("data", [])
    for x in mall:
        pt = float(x.get("point") or 0)
        if pt > 0:
            mall_rows.append({"name": x.get("spuName"), "point": pt})
    mall_rows.sort(key=lambda r: r["point"])
    can = [r for r in mall_rows if r["point"] <= avail][:4]
    nxt = [r for r in mall_rows if r["point"] > avail]

    unclaimed = [a.get("couponName") for a in c.call("available-coupons", {}).get("data", [])
                 if a.get("couponStatus") == "CAN_GET"]

    return {
        "type": "guard",
        "found": True,
        "points": {
            "available": avail,
            "expired": expired,
            "total": acct.get("accumulativePoint", "-"),
        },
        "coupons": coupons,
        "mall_can": can,
        "mall_next": nxt[0] if nxt else None,
        "mall_next_gap": round(nxt[0]["point"] - avail, 1) if nxt else None,
        "unclaimed": unclaimed,
    }
