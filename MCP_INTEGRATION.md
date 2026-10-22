# MCP 集成说明

## 使用的麦当劳 MCP Server

- **服务名称**：麦当劳 MCP（mcd-mcp）
- **接入地址**：https://mcp.mcd.cn
- **传输协议**：Streamable HTTP
- **鉴权方式**：请求头 `Authorization: Bearer <MCP_TOKEN>`
- **开放平台**：https://open.mcd.cn/mcp
- **官方仓库**：https://github.com/M-China/mcd-mcp-server
- **限流**：每个 Token 每分钟 600 次请求

## 实际使用的 Tool

| Tool | 用途 | 调用时机 |
|------|------|---------|
| `query-nearby-stores` | 按城市+关键词查门店 | 用户搜门店 |
| `query-meals` | 拉取门店在售菜单与价格 | 选中门店后 |
| `query-meal-detail` | 套餐默认组成、可替换项、特制项 | 拆解套餐 |
| `list-nutrition-foods` | 160 条餐品营养（热量/蛋白/脂肪/碳水/钠/钙） | 营养求和 |
| `query-store-coupons` | 门店可用券（含券码、适用商品） | 券算价 |
| `calculate-price` | 官方价格计算（含券后价、优惠金额） | 券算价 |
| `auto-bind-coupons` | 一键领取所有可领券 | 用户点「一键全领了」 |
| `available-coupons` | 查可领取未领的券 | 资产页 |
| `query-my-account` | 查询积分账户（可用/累计/过期） | 资产页 |
| `mall-points-products` | 积分商城可兑换商品 | 积分怎么花 |

## 调用流程

```
用户选择「城市 + 区」
  → query-nearby-stores(beType=1, searchType=2, city, keyword)
  → 用户选择门店（storeCode）
  → query-meals(storeCode, orderType=1, beType=1)     # 门店菜单
  → 用户选套餐 A / B
  → query-meal-detail(storeCode, code)                 # 套餐默认组成
  → 本地拆解：组成项 × 单点价 → 真实节省
  → list-nutrition-foods → 组成项营养求和
  → 结论生成（差价、蛋白差、麦当劳度量衡）

资产页：
  query-my-account → 积分
  query-store-coupons + calculate-price → 每张券的用券价与实际节省
  available-coupons → 未领取的券
  auto-bind-coupons → 用户确认后一键领取
```

## 业务价值

- **真实优惠计算**：划线价是营销口径，真实节省 = 拆开单点的合计 - 套餐价。用 `query-meal-detail` 拿真实组成、用菜单价格做单点求和，结论可复现、可核验。
- **官方算价**：券的"实际值多少钱"用 `calculate-price` 官方口径计算（含优惠金额），不是自行估算。
- **真实操作闭环**：`auto-bind-coupons` 让"提醒用户领券"从建议变成可执行动作。

## 技术要点（实测）

1. `list-nutrition-foods` 返回的数据为文本格式（首行字段定义 + 数据行），需解析，不能按固定位置 split（部分字段可能为 null 或含逗号）。
2. 价格单位不一致：`query-meals` 返回「元」，`calculate-price` 返回「分」，展示层必须统一换算。
3. 到店自取场景 `beType=1`，后续调用不再传 `beCode`。
4. 套餐可替换项只能发生在同一 round 的候选项里（实测：板烧三件套的小食轮不含玉米杯）。
5. MCP 偶发超时，客户端做兜底提示（"接口开小差了，稍后再试"）。
