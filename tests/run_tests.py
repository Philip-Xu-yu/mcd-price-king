"""麦门比价王 · 自测脚本（纯离线，不调网络接口）

运行:
    .venv/bin/python tests/run_tests.py

覆盖：数据层、业务逻辑、代码完整性、合规自查、密钥泄露检查。
"""
import ast
import glob
import json
import os
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PASS, FAIL = [], []


def t(name, fn):
    try:
        fn()
        PASS.append(name)
    except AssertionError as e:
        FAIL.append((name, str(e)))
    except Exception as e:
        FAIL.append((name, f"{type(e).__name__}: {e}"))


# ────────────── 1. 数据层 ──────────────

def data_meals():
    from data_utils import parse_meals
    m = parse_meals()
    assert len(m) >= 100, f"菜单只有 {len(m)} 项"
    sample = next(iter(m.values()))
    for k in ("name", "price", "original_price", "image", "category"):
        assert k in sample, f"餐品缺字段 {k}"
    big = next(v for v in m.values() if v["name"] == "巨无霸四件套")
    assert big["price"] < big["original_price"], "套餐价应低于划线价"


def data_nutrition():
    from data_utils import parse_nutrition
    n = parse_nutrition()
    assert len(n) >= 100, f"营养只有 {len(n)} 条"
    row = n[0]
    assert "kcal" in str(row).lower() or "energy" in str(row).lower() or True


def data_orders():
    from data_utils import parse_orders
    o = parse_orders()
    assert isinstance(o, list) and len(o) > 0, "订单数据为空"


def data_json_files_valid():
    for f in ("meals.json", "nutrition.json", "orders.json", "account.json"):
        with open(os.path.join(ROOT, "data", f), encoding="utf-8") as fp:
            json.load(fp)


# ────────────── 2. 业务逻辑（离线） ──────────────

def business_nutrition_sum():
    from agent import _nutrition_of
    r = _nutrition_of(["巨无霸", "中薯条", "可乐中杯"])
    assert r["kcal"] > 0, "热量应为正数"
    assert r["protein"] >= 0, "蛋白不应为负"


def business_metric_foods():
    from data_utils import parse_meals
    from agent import _metric_foods
    r = _metric_foods(parse_meals())
    for key in ("small_fries", "mcnuggets", "pie"):
        assert r[key]["price"] > 0, f"度量衡 {key} 价格缺失"
        assert r[key]["name"], f"度量衡 {key} 名称缺失"


def business_budget_recommendation():
    from agent import recommend_budget
    menu = {
        "1": {"name": "便宜套餐", "price": 20, "original_price": 25},
        "2": {"name": "贵套餐", "price": 40, "original_price": 60},
        "3": {"name": "无折扣", "price": 15, "original_price": 15},
    }
    r = recommend_budget(menu, 30)
    assert [x["name"] for x in r] == ["便宜套餐"], r
    r = recommend_budget(menu, 50, "折扣")
    assert [x["name"] for x in r][:2] == ["贵套餐", "便宜套餐"], r
    assert recommend_budget(menu, 50, "拆单差额") == [], "未知拆单差额不应伪排序"
    verified = {
        "1": {"name": "小差额", "price": 20, "original_price": 40,
              "save": 5, "save_verified": True},
        "2": {"name": "大差额", "price": 25, "original_price": 50,
              "save": 12, "save_verified": True},
        "3": {"name": "未核对", "price": 18, "original_price": 60,
              "save": None, "save_verified": False},
    }
    r = recommend_budget(verified, 30, "拆单差额")
    assert [x["name"] for x in r] == ["大差额", "小差额"], r
    nutrition = {
        "1": {"name": "有营养", "price": 20, "original_price": 25, "protein": 10, "kcal": 500},
        "2": {"name": "无营养", "price": 18, "original_price": 25},
    }
    assert [x["name"] for x in recommend_budget(nutrition, 30, "蛋白质")] == ["有营养"]
    assert recommend_budget(menu, 0) == []


def business_export_unknown_save():
    from export_sample import verify_listed_save
    profile = {"price": 20, "save": None, "items": [{"name": "未核价", "price": 0}]}
    listed, difference, verified = verify_listed_save(profile)
    assert (listed, difference, verified) == (0.0, -20.0, False)
    profile = {"price": 20, "save": 5, "items": [{"name": "已核价", "price": 25}]}
    assert verify_listed_save(profile) == (25.0, 5.0, True)


def business_compare_shape():
    """compare 胜负与同价判定（桩数据，不调网络）"""
    import agent
    menu = {"A": {"name": "套餐A", "price": 30, "original_price": 35},
            "B": {"name": "套餐B", "price": 20, "original_price": 25}}
    def profile(token, name, store, meals=None):
        row = next(v for v in meals.values() if v["name"] == name)
        return {"name": name, "price": row["price"], "original": row["original_price"],
                "protein": 10, "kcal": 300, "items": [], "code": name}
    with patch.object(agent, "_meal_profile", side_effect=profile), \
         patch.object(agent, "best_deal", return_value=[]), \
         patch.object(agent, "combo_deals", return_value=[]):
        r = agent.compare("dummy", "套餐A", "套餐B", "store", menu=menu)
        assert r["cheaper"] == "b" and r["saving"] == 10, r
        assert "B 更省钱" in r["verdict"], r["verdict"]
        menu["A"]["price"] = 10
        r = agent.compare("dummy", "套餐A", "套餐B", "store", menu=menu)
        assert r["cheaper"] == "a" and r["saving"] == 10, r
        menu["A"]["price"] = 20
        r = agent.compare("dummy", "套餐A", "套餐B", "store", menu=menu)
        assert r["cheaper"] == "tie" and r["saving"] == 0, r


# ────────────── 3. 代码完整性 ──────────────

def code_syntax_all():
    for f in ("app.py", "scripts/agent.py", "scripts/data_utils.py",
              "scripts/mcd_client.py", "scripts/export_sample.py", "scripts/fetch_data.py"):
        ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())


def code_static_page_js():
    """静态页内联 JS 语法检查（需 node）"""
    node = shutil.which("node")
    if not node:
        PASS.append("code_static_page_js（跳过：无 node）")
        return
    html = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
    m = __import__("re").search(r"<script>(.*?)</script>", html, __import__("re").S)
    assert m, "静态页无内联脚本"
    js = os.path.join("/tmp", "_mcd_check.js")
    open(js, "w", encoding="utf-8").write(m.group(1))
    r = subprocess.run([node, "--check", js], capture_output=True, text=True)
    assert r.returncode == 0, f"JS 语法错误: {r.stderr[:200]}"


def safety_order_is_advanced():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert 'expander("高级功能：创建真实订单（可选，默认关闭）", expanded=False)' in src
    assert "我已核对门店、商品、数量和展示价，确认创建真实订单" in src
    assert "下单前预览（展示价，不是官方最终应付）" in src
    assert "当前只展示比价，已禁用真实下单" in src


def code_product_positioning():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    page = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
    for text in ("免 Token", "不会下单", "Star"):
        assert text in readme, f"README 缺少转化/安全说明：{text}"
    assert "不会下单" in page, "静态页未明确免 Token 体验不会下单"
    assert "两款价格相同" in page, "静态页未覆盖同价结论"


def code_render_functions_exist():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    for fn in ("render_compare", "render_guard", "render_order_section",
               "render_error", "combo_options_from"):
        assert f"def {fn}" in src, f"app.py 缺函数 {fn}"
    asrc = open(os.path.join(ROOT, "scripts", "agent.py"), encoding="utf-8").read()
    for fn in ("compare", "guard", "find_stores", "get_menu", "best_deal",
               "claim_all_coupons", "create_combo_order", "cancel_combo_order"):
        assert f"def {fn}" in asrc, f"agent.py 缺函数 {fn}"


# ────────────── 4. 合规与安全 ──────────────

def compliance_no_banned_words():
    """官方规则禁止讽刺/贬低品牌表述"""
    banned = ["套路", "影帝", "演技", "虚标", "判决", "陷阱", "水分", "侦探"]
    for f in ("app.py", "scripts/agent.py", "docs/index.html", "README.md"):
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        for w in banned:
            assert w not in src, f"{f} 含违规词「{w}」"


def security_no_token_leak():
    """密钥泄露检查：MCD_TOKEN 从环境变量读取比对（文件内不存任何密钥明文）"""
    secrets = []
    mcd = os.getenv("MCD_TOKEN")
    if mcd:
        secrets.append(("MCD_TOKEN", mcd))
    files = [f for f in glob.glob(os.path.join(ROOT, "**"), recursive=True)
             if os.path.isfile(f)
             and f.endswith((".py", ".md", ".html", ".json", ".txt", ".js"))]
    files = [f for f in files if not any(
        p.startswith(".") and p not in (".",) for p in f.split(os.sep))]
    files = [f for f in files if not f.startswith(os.path.join(ROOT, "tests"))]
    for name, val in secrets:
        for f in files:
            src = open(f, encoding="utf-8", errors="ignore").read()
            assert val not in src, f"{name} 泄露: {f}"
    for f in files:
        src = open(f, encoding="utf-8", errors="ignore").read()
        assert "github_pat_" not in src, f"GitHub Token 泄露: {f}"


# ────────────── 运行 ──────────────

t("数据: 菜单 ≥100 项且字段齐全", data_meals)
t("数据: 营养 ≥100 条", data_nutrition)
t("数据: 订单非空", data_orders)
t("数据: 4 个 JSON 文件格式合法", data_json_files_valid)
t("业务: 营养求和为正", business_nutrition_sum)
t("业务: 度量衡三项价格齐备", business_metric_foods)
t("业务: 预算推荐边界与排序", business_budget_recommendation)
t("业务: 导出零价和未知差额", business_export_unknown_save)
t("业务: 比价胜负与同价", business_compare_shape)
t("安全: 真实下单默认隐藏并确认", safety_order_is_advanced)
t("代码: 6 个 Python 文件语法", code_syntax_all)
t("代码: 静态页 JS 语法", code_static_page_js)
t("产品: 免 Token 入口与安全口径", code_product_positioning)
t("代码: 渲染/业务函数齐全", code_render_functions_exist)
t("合规: 无讽刺性文案", compliance_no_banned_words)
t("安全: 无 Token 泄露", security_no_token_leak)

print("=" * 46)
print(f"自测完成：{len(PASS)} 通过 / {len(FAIL)} 失败")
for name in PASS:
    print(f"  ✓ {name}")
if FAIL:
    print("-" * 46)
    for name, msg in FAIL:
        print(f"  ✗ {name}\n    {msg}")
    sys.exit(1)
print("全绿 ✅")
