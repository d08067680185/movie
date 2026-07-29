"""网盘类型 -> adapter 类的注册表，写法与 spiders/__init__.py:SPIDER_REGISTRY 一致。"""

from pan_transfer.quark import QuarkAdapter

ADAPTER_REGISTRY = {
    "quark": QuarkAdapter,
    # "baidu": BaiduAdapter,
    # "aliyun": AliyunAdapter,
    # "xunlei": XunleiAdapter,
}


def get_adapter(netdisk_type: str):
    adapter_cls = ADAPTER_REGISTRY.get(netdisk_type)
    if adapter_cls is None:
        raise ValueError(f"不支持的网盘类型: {netdisk_type}")
    return adapter_cls()
