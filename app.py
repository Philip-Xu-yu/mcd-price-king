"""麦门比价王 - 套餐比价版

运行:
    MCD_TOKEN=xxx .venv/bin/streamlit run app.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import streamlit as st

import agent

st.set_page_config(page_title="麦门比价王", page_icon="🍔", layout="centered")

# ══════════════════ 主题 ══════════════════
st.markdown("""
<style>
.stApp { background: #FFFDF7; }
.main .block-container { max-width: 900px; padding-top: 1.8rem; }
h1, h2, h3 { color: #DA291C !important; font-weight: 800; }
.stButton > button {
  background: #DA291C; color: white; border: none; border-radius: 10px;
  font-weight: 700; padding: 0.5rem 1.4rem;
}
.stButton > button:hover { background: #B82014; color: white; }
.mcd-hero {
  background: linear-gradient(135deg, #DA291C 0%, #B82014 100%);
  border-radius: 20px; padding: 26px 30px; color: white; margin-bottom: 16px;
}
.mcd-hero h2 { color: white !important; margin: 0; font-size: 1.9rem; }
.mcd-hero p { color: #FFE9B8; margin: 8px 0 0; font-size: 1rem; }
.mcd-tag {
  display: inline-block; background: #FFC72C; color: #7A5200;
  border-radius: 20px; padding: 2px 12px; font-size: 0.78rem; font-weight: 700; margin-right: 6px;
}
.mcd-warn { background: #FFF3E0; border-left: 4px solid #FF9800; padding: 10px 14px; border-radius: 8px; margin: 8px 0; }
.mcd-bad { background: #FFEBEE; border-left: 4px solid #DA291C; padding: 10px 14px; border-radius: 8px; margin: 8px 0; }
.mcd-good { background: #E8F5E9; border-left: 4px solid #4CAF50; padding: 10px 14px; border-radius: 8px; margin: 8px 0; }
.small { color: #888; font-size: 0.8rem; }
.mcd-card {
  background: white; border-radius: 14px; padding: 12px 16px; margin: 6px 0;
  border: 1px solid #F0E6D2; box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.vs-card {
  background: white; border-radius: 16px; padding: 16px; border: 2px solid #F0E6D2;
  height: 100%;
}
.vs-card.win { border-color: #4CAF50; }
.vs-card.lose { border-color: #DDD; }
.metric-line { font-size: 0.92rem; margin: 6px 0; }
.metric-line b { font-size: 1.05rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="mcd-hero">
  <h2>🍔 麦门比价王</h2>
  <p>选择困难？把两个套餐拿来比一比 —— 价格、营养、谁更划算，一目了然。</p>
  <p style="margin-top:10px;font-size:0.85rem;color:#FFD9D4">基于 126 个真实菜单 · 160 条官方营养数据 · 麦当劳 MCP 实时接口</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════ 状态 ══════════════════
with st.sidebar:
    st.markdown("### 🔑 个人数据")
    user_token = st.text_input(
        "MCD Token（查看你自己的券/积分时填）",
        type="password",
        help="不填则用演示账号。申请地址 open.mcd.cn/mcp",
    )
    st.caption("Token 仅存于本次会话，关闭即清。")

TOKEN = (user_token or os.getenv("MCD_TOKEN", "")).strip()


# ══════════════════ 工具 ══════════════════
def safe_run(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return {"type": "error"}


def render_error():
    st.markdown('<div class="mcd-bad">🍟 麦当劳接口开小差了（可能限流或 Token 无效）。'
                '稍等几秒再试，或检查左侧 Token。</div>', unsafe_allow_html=True)


SCENES = {
    "👤 单人餐": ["人气热卖", "精选单人餐", "大堡口福单人餐", "500大卡套餐", "随心配1+1"],
    "🍔 汉堡": ["鸡肉汉堡/卷", "巨无霸牛鱼肉堡", "安格斯MAX厚牛堡"],
    "👥 双人/多人": ["小食拼盘/多人餐"],
    "🍗 炸鸡小食": ["炸鸡", "蘸酱炸鸡", "小食甜品/其他"],
    "👶 开心乐园": ["开心乐园"],
    "🥤 饮品咖啡": ["饮品", "麦咖啡™"],
}


def norm_cat(c):
    return c.replace("\n", "").strip()


@st.cache_data(ttl=3600)
def combo_options_from(meals):
    """meals dict → [(category, name)] 只含有划线价的套餐"""
    grouped = {}
    for code, v in meals.items():
        if v["original_price"] <= v["price"]:
            continue
        cat = norm_cat(v.get("category") or "其他")
        grouped.setdefault(cat, []).append((v["name"], code))
    out = []
    for cat in sorted(grouped.keys()):
        for name, code in grouped[cat]:
            out.append((cat, name))
    return out


def default_menu():
    from data_utils import parse_meals
    return parse_meals()


def render_compare(r):
    """渲染比价结果：并排卡片 + 结论"""
    a, b = r["a"], r["b"]
    cA, cVS, cB = st.columns([5, 1, 5])

    with cA:
        win = r["cheaper"] == "a"
        border = "#4CAF50" if win else "#EEE"
        st.markdown(f'<div style="border:2px solid {border};border-radius:16px;padding:14px;background:white;text-align:center">',
                    unsafe_allow_html=True)
        if a["image"]:
            st.image(a["image"], width=160)
        st.markdown(f'<b style="font-size:1.05rem">{a["name"]}</b>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:1.8rem;font-weight:800;color:#DA291C">¥{a["price"]}</div>'
                    f'<div class="small"><s>划线价 ¥{a["original"]}</s></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-line">真实省 <b>¥{a["save"]}</b></div>'
                    f'<div class="metric-line">热量 <b>{a["kcal"]} kcal</b></div>'
                    f'<div class="metric-line">蛋白 <b>{a["protein"]} g</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with cVS:
        st.markdown('<div style="text-align:center;font-size:1.6rem;font-weight:800;color:#DA291C;padding-top:60px">VS</div>',
                    unsafe_allow_html=True)

    with cB:
        win = r["cheaper"] == "b"
        border = "#4CAF50" if win else "#EEE"
        st.markdown(f'<div style="border:2px solid {border};border-radius:16px;padding:14px;background:white;text-align:center">',
                    unsafe_allow_html=True)
        if b["image"]:
            st.image(b["image"], width=160)
        st.markdown(f'<b style="font-size:1.05rem">{b["name"]}</b>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:1.8rem;font-weight:800;color:#DA291C">¥{b["price"]}</div>'
                    f'<div class="small"><s>划线价 ¥{b["original"]}</s></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-line">真实省 <b>¥{b["save"]}</b></div>'
                    f'<div class="metric-line">热量 <b>{b["kcal"]} kcal</b></div>'
                    f'<div class="metric-line">蛋白 <b>{b["protein"]} g</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 组成明细（两张卡下方并排展示）
    if a.get("items") or b.get("items"):
        ia, ib = st.columns(2)
        for col, x in ((ia, a), (ib, b)):
            with col:
                if x.get("items"):
                    st.markdown(f'<p class="small" style="margin:6px 0 2px">{x["name"]} 包含：</p>',
                                unsafe_allow_html=True)
                    chips = ""
                    for it in x["items"]:
                        p = f"¥{it['price']:.1f}" if it["price"] else "套餐内"
                        chips += (f'<span style="display:inline-block;background:#FFF8E7;border:1px solid #E8DCC3;'
                                  f'border-radius:10px;padding:3px 10px;margin:2px 4px 2px 0;font-size:0.8rem">'
                                  f'{it["name"]} <b style="color:#DA291C">{p}</b></span>')
                    st.markdown(chips, unsafe_allow_html=True)

    # 券自动匹配
    for side, x in (("A", a), ("B", b)):
        deals = x.get("deals") or []
        if deals:
            dl = deals[0]
            st.markdown(
                f'<div class="mcd-good" style="display:flex;justify-content:space-between;align-items:center">'
                f'<div>🎟️ {side} 可用券「{dl["coupon"]}」'
                f'{"（适用于套餐内「" + dl.get("for_item","") + "」）" if dl.get("for_item") else ""}'
                f'<br><span class="small">到期 {dl["expire"]}</span></div>'
                f'<div style="text-align:right"><span style="font-size:1.2rem;font-weight:800;color:#DA291C">¥{dl["price"]}</span>'
                f' <span class="small"><s>¥{dl["original"]}</s></span>'
                f'<br><span class="mcd-tag">省 ¥{dl["discount"]}</span></div></div>',
                unsafe_allow_html=True)

    # 结论卡
    st.markdown(
        f'<div style="border:2px dashed #DA291C;border-radius:14px;padding:14px 18px;margin-top:14px">'
        f'<div style="font-weight:800;color:#DA291C">⚖️ 结论</div>'
        f'<div style="margin-top:6px;font-size:1.02rem">{r["verdict"]}</div>'
        f'<div class="small" style="margin-top:8px">💡 省下的 ¥{r["saving"]} {r["food_txt"]}'
        f'{"；蛋白差 " + r["protein_food"] if r["protein_food"] else ""}</div>'
        f'</div>',
        unsafe_allow_html=True)


def render_guard(d):
    p = d["points"]
    c1, c2, c3 = st.columns(3)
    c1.metric("可用积分", f"{p['available']}")
    c2.metric("已过期积分", f"{p['expired']}")
    c3.metric("累计积分", p["total"])
    if p["expired"] > 0:
        st.markdown(f'<div class="mcd-bad">🚨 <b>{p["expired"]:.0f} 积分</b>已经过期作废 —— 积分也是钱。</div>',
                    unsafe_allow_html=True)

    if d["coupons"]:
        st.markdown("**🎫 你的券（官方算价）：**")
        priced = [cp for cp in d["coupons"] if "discount" in cp]
        best = max(priced, key=lambda x: x["discount"]) if priced else None
        for cp in d["coupons"]:
            if "discount" in cp:
                star = " 👑 全场最值" if (best and cp is best) else ""
                st.markdown(f'<div class="mcd-card" style="display:flex;justify-content:space-between;align-items:center">'
                            f'<div><b>{cp["title"]}</b><span style="color:#DA291C;font-weight:800">{star}</span>'
                            f'<br><span class="small">到期 {cp["expire"]}｜{cp["product"]}</span></div>'
                            f'<div style="text-align:right"><span style="font-size:1.3rem;font-weight:800;color:#DA291C">¥{cp["price"]}</span>'
                            f' <span class="small"><s>¥{cp["original"]}</s></span><br>'
                            f'<span class="mcd-tag">省 ¥{cp["discount"]}</span></div></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="padding:6px 14px"><b>{cp["title"]}</b>'
                            f'<span class="small">（到期 {cp["expire"]}）</span></div>', unsafe_allow_html=True)

    if d["mall_can"]:
        st.markdown("**📦 积分现在就能换：**")
        for r in d["mall_can"]:
            st.markdown(f'<div class="mcd-good" style="margin:4px 0">✅ <b>{r["name"]}</b> —— {r["point"]:.0f} 积分</div>',
                        unsafe_allow_html=True)
    if d["mall_next"]:
        st.markdown(f'<div class="mcd-warn">📈 再攒 <b>{d["mall_next_gap"]}</b> 分能换「{d["mall_next"]["name"]}」</div>',
                    unsafe_allow_html=True)
    if d["unclaimed"]:
        st.markdown("**✚ 麦当劳想请你吃，你还没收：**")
        for n in d["unclaimed"]:
            st.markdown(f'<div class="mcd-warn" style="margin:4px 0">✚ <b>{n}</b> —— 去 App 领掉它</div>',
                        unsafe_allow_html=True)
        if st.button("一键全领了", type="primary", key="claim_btn"):
            with st.spinner("正在领取..."):
                r = safe_run(agent.claim_all_coupons, TOKEN)
            if r and r.get("type") == "error":
                render_error()
            else:
                if r["success"]:
                    st.markdown(f'<div class="mcd-good">🎉 已领取：{", ".join(r["success"])}</div>',
                                unsafe_allow_html=True)
                if r["failed"]:
                    st.markdown(f'<div class="mcd-warn">领取失败：{", ".join(r["failed"])}</div>',
                                unsafe_allow_html=True)


# ══════════════════ 页面 ══════════════════
tab1, tab2 = st.tabs(["⚖️ 套餐比价", "💎 我的券和积分"])

with tab1:
    if not TOKEN:
        st.warning("未设置 MCD_TOKEN。请在启动时设置环境变量，或在左侧填入你的 Token。")
    else:
        # ── ① 门店 ──
        DISTRICTS = {
            "广州": ["天河区", "越秀区", "海珠区", "白云区", "荔湾区", "黄埔区",
                     "番禺区", "花都区", "南沙区", "增城区", "从化区", "（不限）"],
            "深圳": ["南山区", "福田区", "罗湖区", "宝安区", "龙岗区", "龙华区", "（不限）"],
            "佛山": ["禅城区", "南海区", "顺德区", "（不限）"],
            "清远": ["清城区", "清新区", "（不限）"],
        }
        st.markdown("**① 选门店**")
        sc1, sc2, sc3 = st.columns([2, 2, 1])
        with sc1:
            city = st.selectbox("城市", list(DISTRICTS.keys()), label_visibility="collapsed")
        with sc2:
            district = st.selectbox("区/县", DISTRICTS[city], label_visibility="collapsed")
        with sc3:
            search = st.button("搜门店", use_container_width=True)

        if search:
            kw = "" if "不限" in district else district.replace("区", "").replace("县", "")
            with st.spinner("搜索门店中..."):
                stores = safe_run(agent.find_stores, TOKEN, city, kw)
            if stores == {"type": "error"} or not stores:
                st.warning(f"没搜到 {city}{district} 的门店，换个区试试。")
            else:
                st.session_state.stores = stores
                st.session_state.pop("store_menu", None)

        if st.session_state.get("stores"):
            stores = st.session_state.stores
            cols = st.columns(2)
            for i, s in enumerate(stores):
                with cols[i % 2]:
                    dist = s.get("distance")
                    dist_txt = f"距你 {dist} 米" if dist else ""
                    active = st.session_state.get("store_code") == s["code"]
                    border = "2px solid #DA291C" if active else "1px solid #F0E6D2"
                    st.markdown(
                        f'<div style="border:{border};border-radius:12px;padding:8px 12px;margin:4px 0;background:white">'
                        f'<b>📍 {s["name"]}</b><br>'
                        f'<span class="small">{s.get("address","")}｜{dist_txt}</span></div>',
                        unsafe_allow_html=True)
                    if st.button("选这家", key=f"store_{i}", use_container_width=True):
                        st.session_state.store_code = s["code"]
                        st.session_state.pop("store_menu", None)
                        st.session_state.pop("cmp_a", None)
                        st.session_state.pop("cmp_b", None)
                        st.session_state.pop("cmp_result", None)
                        st.rerun()

            if st.session_state.get("store_code") and not st.session_state.get("store_menu"):
                with st.spinner("加载该门店菜单..."):
                    menu = safe_run(agent.get_menu, TOKEN, st.session_state.store_code)
                if menu != {"type": "error"} and menu:
                    st.session_state.store_menu = menu

        store_code = st.session_state.get("store_code")
        cur_meals = st.session_state.get("store_menu")
        opts = combo_options_from(cur_meals) if cur_meals else combo_options_from(default_menu())

        # 当前门店状态条（常驻）
        if store_code and st.session_state.get("stores"):
            for s in st.session_state.stores:
                if s["code"] == store_code:
                    st.markdown(
                        f'<div style="background:#FFF8E7;border:1px solid #FFC72C;border-radius:10px;'
                        f'padding:6px 12px;margin:8px 0;font-size:0.88rem">'
                        f'📍 当前门店：<b>{s["name"]}</b>｜{s.get("address","")}'
                        f'{"｜距你 " + str(s["distance"]) + " 米" if s.get("distance") else ""}</div>',
                        unsafe_allow_html=True)
                    break

        # ── ② 选套餐比价 ──
        st.markdown("**② 选两个套餐比一比**")

        # 场景 → 细分类 双排胶囊
        scene_map = {s: [] for s in SCENES}
        for cat, name in opts:
            c = norm_cat(cat)
            for scene, kws in SCENES.items():
                if c in kws:
                    scene_map[scene].append((cat, name))
                    break
            else:
                scene_map.setdefault("📦 其他", []).append((cat, name))
        scene_map = {k: v for k, v in scene_map.items() if v}

        if not scene_map:
            st.warning("该门店菜单为空。")
        else:
            scenes = list(scene_map.keys())
            if "sel_scene" not in st.session_state or st.session_state.sel_scene not in scenes:
                st.session_state.sel_scene = scenes[0]
            st.session_state.sel_scene = st.pills("场景", scenes, key="scene_pills",
                                                  default=st.session_state.sel_scene)

            sub_cats = []
            for cat, _ in scene_map[st.session_state.sel_scene]:
                if cat not in sub_cats:
                    sub_cats.append(cat)
            if "sel_sub" not in st.session_state or st.session_state.sel_sub not in sub_cats:
                st.session_state.sel_sub = sub_cats[0] if sub_cats else None
            if sub_cats:
                st.session_state.sel_sub = st.pills("分类", sub_cats, key="sub_pills",
                                                    default=st.session_state.sel_sub)

            sub = [(c, n) for (c, n) in scene_map[st.session_state.sel_scene]
                   if c == st.session_state.sel_sub]

            # 卡片网格
            COLS = 3
            grid = st.columns(COLS)
            for i, (cat, name) in enumerate(sub):
                code = None
                if cur_meals:
                    for c2, v2 in cur_meals.items():
                        if v2["name"] == name:
                            code = c2
                            break
                img = price = orig = ""
                if cur_meals and code:
                    img = cur_meals[code].get("image", "")
                    price = cur_meals[code]["price"]
                    orig = cur_meals[code]["original_price"]
                with grid[i % COLS]:
                    if img:
                        st.image(img, width=130)
                    st.markdown(f'<b style="font-size:0.88rem">{name}</b>', unsafe_allow_html=True)
                    if price != "":
                        st.markdown(f'<span style="color:#DA291C;font-weight:800">¥{price}</span>'
                                    f' <span class="small"><s>¥{orig}</s></span>', unsafe_allow_html=True)
                    # 加入比价槽
                    in_a = st.session_state.get("cmp_a") == name
                    in_b = st.session_state.get("cmp_b") == name
                    label = "✓ 已选 A" if in_a else ("✓ 已选 B" if in_b else "加入比价")
                    disabled = in_a or in_b
                    if st.button(label, key=f"add_{cat}_{name}", use_container_width=True,
                                 disabled=disabled):
                        if not st.session_state.get("cmp_a"):
                            st.session_state.cmp_a = name
                        elif not st.session_state.get("cmp_b"):
                            st.session_state.cmp_b = name
                        else:
                            st.session_state.cmp_a, st.session_state.cmp_b = name, None
                        st.session_state.pop("cmp_result", None)
                        st.rerun()

        # ── 比价槽 ──
        cmp_a = st.session_state.get("cmp_a")
        cmp_b = st.session_state.get("cmp_b")
        if cmp_a or cmp_b:
            st.markdown("**③ 比一比**")
            slot1, slot2 = st.columns(2)
            with slot1:
                st.markdown(f'<div class="mcd-card" style="text-align:center">'
                            f'<div class="small">A 位</div><b>{cmp_a or "待选择"}</b></div>',
                            unsafe_allow_html=True)
            with slot2:
                st.markdown(f'<div class="mcd-card" style="text-align:center">'
                            f'<div class="small">B 位</div><b>{cmp_b or "待选择"}</b></div>',
                            unsafe_allow_html=True)
            col_go, col_clr = st.columns([2, 1])
            with col_go:
                if st.button("开始比价 ⚖️", type="primary", use_container_width=True,
                             disabled=not (cmp_a and cmp_b)):
                    with st.spinner("计算中..."):
                        r = safe_run(agent.compare, TOKEN, cmp_a, cmp_b, store_code)
                    if r == {"type": "error"}:
                        render_error()
                    elif not r.get("found"):
                        st.warning(r.get("reason") or f"没找到「{cmp_a}」或「{cmp_b}」。")
                    else:
                        st.session_state.cmp_result = r
            with col_clr:
                if st.button("清空", use_container_width=True):
                    st.session_state.pop("cmp_a", None)
                    st.session_state.pop("cmp_b", None)
                    st.session_state.pop("cmp_result", None)
                    st.rerun()

        # ── 结果（默认首屏示例）──
        if "cmp_result" in st.session_state:
            render_compare(st.session_state.cmp_result)
        elif not cmp_a and not cmp_b:
            with st.spinner("准备示例比价..."):
                r = safe_run(agent.compare, TOKEN, "巨无霸四件套", "板烧鸡腿堡四件套", store_code)
            if r != {"type": "error"} and r.get("found"):
                st.markdown('<p class="small" style="margin-top:10px">👇 示例：巨无霸四件套 vs 板烧鸡腿堡四件套（选择困难，直接看结论）</p>',
                            unsafe_allow_html=True)
                render_compare(r)

with tab2:
    st.markdown("### 券和积分，别让它们悄悄过期")
    if not TOKEN:
        st.warning("未设置 MCD_TOKEN。请在启动时设置环境变量，或在左侧填入你的 Token。")
    else:
        # 自动展示，不再要求点按钮
        if "guard_data" not in st.session_state:
            with st.spinner("官方算价中..."):
                st.session_state.guard_data = safe_run(agent.guard, TOKEN)
        data = st.session_state.guard_data
        if data.get("type") == "error":
            render_error()
        else:
            render_guard(data)
        if st.button("🔄 刷新", use_container_width=True):
            with st.spinner("官方算价中..."):
                st.session_state.guard_data = safe_run(agent.guard, TOKEN)
            st.rerun()

st.markdown("---")
st.markdown('<p class="small" style="text-align:center">🍔 麦门比价王 · 数据来源：麦当劳官方 MCP 实时接口 · 价格以门店为准</p>',
            unsafe_allow_html=True)
