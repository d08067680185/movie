"""网盘转存适配层的公共接口/异常类型。

各家网盘(夸克/百度/阿里云盘/迅雷)目前都没有面向个人开发者、可直接调用的官方
"转存到自己网盘"开放API，这里的实现基于社区逆向出来的私有接口(cookie/token鉴权)。
这类接口会随对方前端改版随时失效，属于不稳定的第三方依赖，因此:
  - 所有网络调用集中在各自的 adapter 文件里，互不影响，一家失效不拖累其他家
  - 统一抛出下面几种语义化异常，上层 worker 据此决定重试/标记账号风险/直接判失败
"""

from abc import ABC, abstractmethod
from typing import Optional


class TransferError(Exception):
    """转存过程中的通用失败(网络错误、对方接口返回未知错误码等)，上层可重试。"""


class RiskControlError(TransferError):
    """账号被网盘风控限制(验证码/频率限制/账号异常)，上层应将账号标记为 risk_limited 并停止使用。"""


class QuotaExceededError(TransferError):
    """网盘账号容量已满，无法继续转存。"""


class ShareInvalidError(TransferError):
    """源分享链接已失效/被取消分享/提取码错误，重试无意义，应直接判失败。"""


class BaseTransferAdapter(ABC):
    """每个网盘类型实现一个子类。credential 是解密后的明文 cookie/token 字符串。"""

    @abstractmethod
    async def transfer(self, credential: str, share_url: str, password: Optional[str]) -> str:
        """把 share_url 指向的分享内容转存到本账号网盘根目录，返回转存后的文件/目录 fid。

        失败时抛出 ShareInvalidError / RiskControlError / QuotaExceededError / TransferError。
        """

    @abstractmethod
    async def create_share(self, credential: str, file_id: str) -> tuple[str, Optional[str]]:
        """为已转存的文件创建新的分享链接，返回 (url, password)。"""

    @abstractmethod
    async def check_quota(self, credential: str) -> tuple[float, float]:
        """返回 (已用GB, 总容量GB)。"""
