"""yt-dlp 封装：下载 YouTube/腾讯视频/优酷等通用视频链接。
海外平台(YouTube 等)支持成熟稳定；国内平台(腾讯视频/优酷等)有加密流+反爬机制，
yt-dlp 对它们的支持经常不稳定、平台改版可能随时失效，属于"尽力而为"。

进度追踪：yt-dlp 的 progress_hooks 在下载线程(非事件循环)里同步调用，不能在其中
await 数据库写入，所以进度先写进程内内存字典(参考 tasks.py 的既有模式)，只有
最终 complete/error 状态由调用方(api/downloads.py)在事件循环里落库。
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)

# 限制画质/体积，避免单个任务占用过多磁盘和下载时长
FORMAT_SELECTOR = "bv*[height<=1080]+ba/b[height<=1080]"

# 卡死的 yt-dlp 线程无法被 Python 强制杀死；用独立、有界的线程池而不是
# asyncio.to_thread 默认的共享执行器，这样即使真的卡死，最坏情况也只占满
# 这 8 个槽位，不会连累全站其他用到默认线程池的地方
_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ytdlp")

_progress: dict[int, dict] = {}


class DownloadError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def get_progress(task_id: int) -> Optional[dict]:
    return _progress.get(task_id)


def clear_progress(task_id: int):
    _progress.pop(task_id, None)


def _run_download(url: str, download_dir: str, task_id: int) -> dict:
    """同步阻塞下载，在线程里跑。返回 {file_path, total_bytes, title}。"""
    outtmpl = os.path.join(download_dir, f"{task_id}_%(title).100s.%(ext)s")

    def hook(d: dict):
        try:
            if d.get("status") == "downloading":
                _progress[task_id] = {
                    "downloaded_bytes": d.get("downloaded_bytes") or 0,
                    "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate"),
                    "speed": d.get("speed"),
                }
        except Exception:
            logger.exception("progress hook 更新失败 task_id=%s", task_id)

    opts = {
        "format": FORMAT_SELECTOR,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        # 堵住绝大多数"卡在网络读取"的真实场景(服务器不响应/DNS超时/TLS握手挂起)
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise DownloadError("无法从该链接提取到视频信息，该网站/页面可能不受支持")
        file_path = ydl.prepare_filename(info)
        # merge_output_format 可能让最终文件后缀变为 mp4，prepare_filename 给的是合并前的名字
        base, _ = os.path.splitext(file_path)
        merged_path = base + ".mp4"
        final_path = merged_path if os.path.exists(merged_path) else file_path
        if not os.path.exists(final_path):
            # 部分网站(如国内视频平台)的通用提取器会"假成功"——返回 info 但实际未下到文件
            raise DownloadError("未能下载到实际视频文件，该网站/页面暂不支持")
        return {
            "file_path": final_path,
            "total_bytes": os.path.getsize(final_path),
            "title": info.get("title") or url,
        }


async def download(url: str, download_dir: str, task_id: int) -> dict:
    """异步包装：yt-dlp 本身同步阻塞，用独立线程池跑(不用 asyncio.to_thread
    默认共享执行器，见 _DOWNLOAD_EXECUTOR 注释)。"""
    os.makedirs(download_dir, exist_ok=True)
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_DOWNLOAD_EXECUTOR, _run_download, url, download_dir, task_id)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e
    finally:
        clear_progress(task_id)
