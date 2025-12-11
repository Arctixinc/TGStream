import asyncio
import subprocess
import os

class HLSOutputServer:
    """
    Accepts TS chunks and writes them to rotating HLS segments.
    """

    def __init__(self, out_dir="hls", segment_time=2):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.proc = None

        self.proc = asyncio.create_task(self.run_ffmpeg(segment_time))

    async def run_ffmpeg(self, segment_time):
        self.ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-fflags", "nobuffer",
            "-i", "pipe:0",
            "-codec", "copy",
            "-f", "hls",
            "-hls_time", str(segment_time),
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments+append_list+omit_endlist",
            f"{self.out_dir}/index.m3u8",
            stdin=subprocess.PIPE
        )

    async def push(self, ts_bytes: bytes):
        if self.ffmpeg:
            try:
                self.ffmpeg.stdin.write(ts_bytes)
                await self.ffmpeg.stdin.drain()
            except Exception:
                pass
