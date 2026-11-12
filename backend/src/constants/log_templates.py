"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "http.mutation": "写请求",
    "carrier.update": "更新承运商配置",
    "track.pull": "拉取承运商轨迹",
    "track.normalize": "执行轨迹归一",
    "mapping.version.create": "创建映射版本",
    "mapping.version.activate": "启用映射版本",
    "alert.claim": "认领停滞预警",
    "alert.dispose": "处置停滞预警",
    "report.export": "导出延迟说明",
}
