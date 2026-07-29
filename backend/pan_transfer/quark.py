"""夸克网盘转存适配器。

夸克官方没有开放平台，这里对接的是夸克网盘网页版(drive-pc.quark.cn)使用的私有接口，
鉴权方式是把网页登录后的完整 Cookie 字符串原样带上。这套接口是社区逆向出来的
(quark-auto-save 等开源项目采用的同一套流程)，未来随时可能因为对方改版而失效，
需要跟进社区更新调整；本文件只做流程封装，不做防混淆/加密参数处理。

流程: 取分享 token -> 拉取分享文件列表 -> 提交转存任务 -> 轮询任务完成 -> 为转存后的
文件创建新分享 -> 轮询分享任务完成 -> 取分享口令。
"""

import asyncio
import re
from typing import Optional

import httpx

from pan_transfer.base import (
    BaseTransferAdapter, TransferError, RiskControlError, QuotaExceededError, ShareInvalidError,
)

BASE_URL = "https://drive-pc.quark.cn/1/clouddrive"
QUERY = {"pr": "ucpro", "fr": "pc"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _extract_pwd_id(share_url: str) -> str:
    m = re.search(r"/s/([a-zA-Z0-9]+)", share_url)
    if not m:
        raise ShareInvalidError(f"无法从链接解析夸克分享ID: {share_url}")
    return m.group(1)


class QuarkAdapter(BaseTransferAdapter):
    def _headers(self, credential: str) -> dict:
        return {"Cookie": credential, "User-Agent": UA, "Content-Type": "application/json"}

    async def _poll_task(self, client: httpx.AsyncClient, credential: str, task_id: str) -> dict:
        for _ in range(20):
            resp = await client.get(
                f"{BASE_URL}/task", params={**QUERY, "task_id": task_id, "retry_index": 0},
                headers=self._headers(credential),
            )
            data = resp.json()
            status = data.get("data", {}).get("status")
            if status == 2:  # 完成
                return data["data"]
            if status == 3:  # 失败
                raise TransferError(f"夸克任务失败: {data.get('data', {}).get('task_title')}")
            await asyncio.sleep(1)
        raise TransferError("夸克任务轮询超时")

    async def transfer(self, credential: str, share_url: str, password: Optional[str]) -> str:
        pwd_id = _extract_pwd_id(share_url)
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                f"{BASE_URL}/share/sharepage/token", params=QUERY,
                json={"pwd_id": pwd_id, "passcode": password or ""},
                headers=self._headers(credential),
            )
            token_data = token_resp.json()
            if token_data.get("status") != 200 or not token_data.get("data", {}).get("stoken"):
                msg = token_data.get("message", "")
                if "密码" in msg or "提取码" in msg:
                    raise ShareInvalidError(f"夸克提取码错误: {msg}")
                if "失效" in msg or "取消" in msg or "不存在" in msg:
                    raise ShareInvalidError(f"夸克分享已失效: {msg}")
                raise TransferError(f"夸克取分享token失败: {msg}")
            stoken = token_data["data"]["stoken"]

            detail_resp = await client.get(
                f"{BASE_URL}/share/sharepage/detail",
                params={**QUERY, "pwd_id": pwd_id, "stoken": stoken, "pdir_fid": "0",
                        "force": "0", "_page": "1", "_size": "50", "_fetch_banner": "0",
                        "_fetch_share": "1", "_fetch_total": "1"},
                headers=self._headers(credential),
            )
            detail_data = detail_resp.json()
            file_list = detail_data.get("data", {}).get("list", [])
            if not file_list:
                raise ShareInvalidError("夸克分享内容为空或已失效")
            fid_list = [f["fid"] for f in file_list]
            fid_token_list = [f["share_fid_token"] for f in file_list]

            save_resp = await client.post(
                f"{BASE_URL}/share/sharepage/save", params=QUERY,
                json={"fid_list": fid_list, "fid_token_list": fid_token_list,
                      "to_pdir_fid": "0", "pwd_id": pwd_id, "stoken": stoken,
                      "pdir_fid": "0", "scene": "link"},
                headers=self._headers(credential),
            )
            save_data = save_resp.json()
            if save_data.get("status") != 200:
                msg = save_data.get("message", "")
                if "容量" in msg or "空间" in msg:
                    raise QuotaExceededError(f"夸克容量不足: {msg}")
                if "频繁" in msg or "验证" in msg or "异常" in msg:
                    raise RiskControlError(f"夸克风控限制: {msg}")
                raise TransferError(f"夸克提交转存失败: {msg}")
            task_id = save_data["data"]["task_id"]

            result = await self._poll_task(client, credential, task_id)
            saved_fids = result.get("save_as", {}).get("save_as_top_fids", [])
            if not saved_fids:
                raise TransferError("夸克转存任务完成但未返回文件ID")
            return saved_fids[0]

    async def create_share(self, credential: str, file_id: str) -> tuple[str, Optional[str]]:
        async with httpx.AsyncClient(timeout=30) as client:
            share_resp = await client.post(
                f"{BASE_URL}/share", params=QUERY,
                json={"fid_list": [file_id], "title": "分享", "url_type": 1, "expired_type": 1},
                headers=self._headers(credential),
            )
            share_data = share_resp.json()
            if share_data.get("status") != 200:
                raise TransferError(f"夸克创建分享失败: {share_data.get('message')}")
            task_id = share_data["data"]["task_id"]
            result = await self._poll_task(client, credential, task_id)
            share_id = result.get("share_id")
            if not share_id:
                raise TransferError("夸克分享任务完成但未返回share_id")

            pwd_resp = await client.post(
                f"{BASE_URL}/share/password", params=QUERY,
                json={"share_id": share_id}, headers=self._headers(credential),
            )
            pwd_data = pwd_resp.json().get("data", {})
            share_url = pwd_data.get("share_url")
            passcode = pwd_data.get("passcode") or None
            if not share_url:
                raise TransferError("夸克未返回最终分享链接")
            return share_url, passcode

    async def check_quota(self, credential: str) -> tuple[float, float]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/member", params=QUERY, headers=self._headers(credential),
            )
            data = resp.json().get("data", {})
            total = data.get("total_capacity", 0)
            used = data.get("use_capacity", 0)
            gb = 1024 ** 3
            return round(used / gb, 2), round(total / gb, 2)
