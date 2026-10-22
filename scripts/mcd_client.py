"""麦当劳 MCP 客户端 - 纯标准库实现，无第三方依赖

用法:
    from mcd_client import MCDClient
    c = MCDClient(token="xxx")
    result = c.call("list-nutrition-foods", {})
"""
import json
import os
import re
import urllib.request


class MCDClient:
    URL = "https://mcp.mcd.cn"

    def __init__(self, token: str = None):
        self.token = token or os.getenv("MCD_TOKEN")
        if not self.token:
            raise ValueError("缺少 MCD_TOKEN，请通过环境变量提供")

    def call(self, tool: str, arguments: dict) -> dict:
        """调用一个 MCP 工具，返回解析后的 JSON 对象"""
        text = self.call_text(tool, arguments)
        return self._extract_json(text)

    def call_raw(self, tool: str, arguments: dict) -> dict:
        """调用 MCP 工具，返回完整响应（含 structuredContent）"""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        req = urllib.request.Request(
            self.URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")

        outer = json.loads(raw)
        if "error" in outer:
            raise RuntimeError(f"MCP 调用失败: {outer['error']}")
        return outer.get("result", {})

    def call_structured(self, tool: str, arguments: dict) -> dict:
        """优先取 structuredContent（官方已解析好的 JSON），回退到文本解析"""
        result = self.call_raw(tool, arguments)
        sc = result.get("structuredContent")
        if isinstance(sc, dict) and sc:
            return sc
        content = result.get("content") or []
        text = content[0].get("text", "") if content else ""
        return self._extract_json(text)

    def call_text(self, tool: str, arguments: dict) -> str:
        """调用 MCP 工具，返回原始文本（适合返回 markdown 的工具）"""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        req = urllib.request.Request(
            self.URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")

        outer = json.loads(raw)
        if "error" in outer:
            raise RuntimeError(f"MCP 调用失败: {outer['error']}")
        content = outer["result"]["content"]
        if not content:
            return ""
        return content[0].get("text", "")

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从 MCP 返回文本中提取 JSON。
        优先找 {"success":... 这种完整响应；找不到再找 '## Original Response' 之后的 JSON"""
        # 方法1：找 {"success" 开头的大 JSON（用 raw_decode 尝试每个候选位置）
        candidates = [m.start() for m in re.finditer(r'\{"success"', text)]
        decoder = json.JSONDecoder()
        for pos in candidates:
            try:
                obj, _ = decoder.raw_decode(text[pos:])
                return obj
            except json.JSONDecodeError:
                continue
        # 方法2：'## Original Response' 之后
        marker = "## Original Response"
        idx = text.find(marker)
        s = text[idx + len(marker):] if idx >= 0 else text
        brace = s.find("{")
        if brace >= 0:
            try:
                obj, _ = decoder.raw_decode(s[brace:])
                return obj
            except json.JSONDecodeError:
                pass
        return {}
