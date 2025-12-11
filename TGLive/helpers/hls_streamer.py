import asyncio
import shutil
from pathlib import Path
from TGLive.logger import LOGGER

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class HLSStreamSession:
    """
    ffmpeg → HLS writer
    Uses delete_segments (auto deletion)
    """

    def __init__(self, out_dir="./hls", playlist="live.m3u8", seg=4, list_size=15):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.playlist_path = self.out_dir / playlist
        self.segment_pattern = str(self.out_dir / "segment_%05d.ts")

        self.seg = seg
        self.list_size = list_size
        self.process = None
        self.stopped = False

    # ---------------------------------------------------------
    def build_cmd(self):
        return [
            FFMPEG,
            "-hide_banner", "-loglevel", "info",
            "-fflags", "+genpts",
            "-re",
            "-i", "pipe:0",
            "-c", "copy",
            "-map", "0",
            "-f", "hls",
            "-hls_time", str(self.seg),
            "-hls_list_size", str(self.list_size),
            "-hls_flags", "delete_segments",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", self.segment_pattern,
            str(self.playlist_path)
        ]

    # ---------------------------------------------------------
    async def start(self):
        if self.process and self.process.returncode is None:
            return

        cmd = self.build_cmd()
        LOGGER.info("Starting ffmpeg: " + " ".join(cmd))

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        asyncio.create_task(self.log_stderr())

    async def log_stderr(self):
        if not self.process:
            return
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                LOGGER.debug("ffmpeg: " + line.decode(errors="ignore"))
        except:
            pass

    # ---------------------------------------------------------
    async def feed_from(self, generator):
        await self.start()

        writer = self.process.stdin

        try:
            async for chunk in generator:
                if self.stopped:
                    break
                if not chunk:
                    continue

                writer.write(chunk)
                await writer.drain()

        except Exception as e:
            LOGGER.error(f"HLS feed error: {e}")

        finally:
            try:
                writer.close()
            except:
                pass

            LOGGER.info("HLS finished.")
            
    # ---------------------------------------------------------
    async def stop(self):
        self.stopped = True
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except:
                self.process.kill()
                
                
    # ---------------------------------------------------------
    def get_playlist_path(self) -> str:
        return str(self.playlist_path.resolve())
