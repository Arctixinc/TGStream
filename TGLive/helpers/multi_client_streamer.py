# # TGLive/helpers/multi_client_streamer.py (stream_video body)
# import asyncio
# from TGLive.logger import LOGGER
# from TGLive.helpers.bot import work_loads

# class MultiClientStreamer:
#     def __init__(self, byte_streamer):
#         self.bs = byte_streamer

#     def _choose_least_loaded_index(self) -> int:
#         if not work_loads:
#             return 0
#         return min(work_loads.keys(), key=lambda k: work_loads.get(k, 0))

#     async def stream_video(self, chat_id: int, message_id: int, start_offset=0):
#         # 1. Get file properties (cached)
#         file_info = await self.bs.get_file_properties(chat_id, message_id)

#         part_count = (file_info.file_size // (512 * 1024)) + 1 if getattr(file_info, "file_size", 0) else 1
#         index = self._choose_least_loaded_index()

#         LOGGER.info(f"MultiClientStreamer: streaming message={message_id} size={getattr(file_info,'file_size',None)} bytes using client_index={index} (parts={part_count})")

#         async for chunk in self.bs.yield_file(
#             file_id=file_info,
#             index=index,
#             offset=start_offset,
#             chunk_size=512 * 1024,
#             part_count=part_count,
#         ):
#             if not chunk:
#                 break
#             # optionally small debug for each chunk (comment out if noisy)
#             LOGGER.debug(f"MultiClientStreamer: yielded chunk for message={message_id} size={len(chunk)}")
#             yield chunk




# TGLive/helpers/multi_client_streamer.py
# import asyncio
# from TGLive.logger import LOGGER
# from TGLive.helpers.bot import work_loads
# from TGLive.helpers.byte_streamer import ByteStreamer
# from typing import AsyncGenerator


# class MultiClientStreamer:
#     """
#     Converts Telegram file bytes -> MPEG-TS (ffmpeg) and yields TS chunks.
#     Caller should feed these TS chunks into a single long-running HLS ffmpeg stdin.
#     """

#     def __init__(self, byte_streamer: ByteStreamer):
#         self.bs = byte_streamer

#     def _choose_least_loaded_index(self) -> int:
#         if not work_loads:
#             return 0
#         return min(work_loads.keys(), key=lambda k: work_loads.get(k, 0))

#     async def _pump_raw_to_ffmpeg(self, ffmpeg_proc, file_id, index, start_offset, part_count):
#         """
#         Pumps raw telegram chunks into ffmpeg's stdin (pipe:0).
#         Runs as a background task so we can read ffmpeg stdout concurrently.
#         """
#         try:
#             async for chunk in self.bs.yield_file(
#                 file_id=file_id,
#                 index=index,
#                 offset=start_offset,
#                 chunk_size=512 * 1024,
#                 part_count=part_count,
#             ):
#                 if not chunk:
#                     continue
#                 try:
#                     ffmpeg_proc.stdin.write(chunk)
#                     await ffmpeg_proc.stdin.drain()
#                 except (BrokenPipeError, ConnectionResetError):
#                     LOGGER.warning("ffmpeg_clean stdin broken while pumping raw bytes.")
#                     break
#         except Exception as e:
#             LOGGER.error(f"Error pumping raw bytes to ffmpeg: {e}", exc_info=True)
#         finally:
#             # Close ffmpeg stdin to signal end-of-file for this input file
#             try:
#                 ffmpeg_proc.stdin.close()
#             except Exception:
#                 pass

#     async def stream_video(self, chat_id: int, message_id: int, start_offset: int = 0) -> AsyncGenerator[bytes, None]:
#         """
#         Yields MPEG-TS chunks converted from the Telegram file.
#         This runs ffmpeg per-file to convert container -> mpegts, but yields TS to be concatenated.
#         """
#         # 1. Get file properties (cached)
#         file_info = await self.bs.get_file_properties(chat_id, message_id)

#         # compute part_count safely
#         file_size = getattr(file_info, "file_size", 0) or 0
#         part_count = (file_size // (512 * 1024)) + 1 if file_size else 1

#         index = self._choose_least_loaded_index()

#         LOGGER.info(
#             f"MultiClientStreamer: streaming message={message_id} size={file_size} bytes using client_index={index} (parts={part_count})"
#         )

#         # Start ffmpeg that converts incoming raw container bytes -> mpegts
#         # ffmpeg_clean = await asyncio.create_subprocess_exec(
#         #     "ffmpeg",
#         #     "-y",               # overwrite if needed (safe for pipe)
#         #     "-loglevel", "error",
#         #     "-i", "pipe:0",     # input from stdin (raw telegram bytes)
#         #     "-map", "0:v",
#         #     "-map", "0:a?",     # include audio if present
#         #     "-c:v", "copy",
#         #     "-c:a", "copy",
#         #     "-f", "mpegts",     # important: output mpegts for concatenation
#         #     "pipe:1",
#         #     stdin=asyncio.subprocess.PIPE,
#         #     stdout=asyncio.subprocess.PIPE,
#         #     stderr=asyncio.subprocess.PIPE,
#         # )
#         ffmpeg_clean = await asyncio.create_subprocess_exec(
#             "ffmpeg",
#             "-y",
#             "-loglevel", "error",
#             "-fflags", "+genpts",
#             "-i", "pipe:0",
#             "-map", "0:v",
#             "-map", "0:a?",
#             "-c:v", "copy",
#             "-c:a", "aac",
#             "-b:a", "128k",
#             "-ac", "2",
#             "-f", "mpegts",
#             "pipe:1",
#             stdin=asyncio.subprocess.PIPE,
#             stdout=asyncio.subprocess.PIPE,
#             stderr=asyncio.subprocess.PIPE,
#         )


#         # Start background pump of raw TG bytes into ffmpeg_clean.stdin
#         pump_task = asyncio.create_task(
#             self._pump_raw_to_ffmpeg(ffmpeg_clean, file_info, index, start_offset, part_count)
#         )

#         # Read ffmpeg_clean stdout (TS packets) and yield to caller
#         try:
#             # Read in reasonable chunks (multiple of TS packet 188 recommended but not required)
#             READ_SIZE = 188 * 64  # ~12032 bytes; tune if you want larger/smaller
#             while True:
#                 data = await ffmpeg_clean.stdout.read(READ_SIZE)
#                 if not data:
#                     break
#                 yield data

#             # Wait for pump to finish (it closes stdin when done)
#             await pump_task
#             # Ensure ffmpeg exits
#             try:
#                 await ffmpeg_clean.wait()
#             except Exception:
#                 pass

#         except asyncio.CancelledError:
#             LOGGER.info("MultiClientStreamer stream_video cancelled; terminating ffmpeg_clean.")
#             try:
#                 ffmpeg_clean.kill()
#             except Exception:
#                 pass
#             raise

#         except Exception as e:
#             LOGGER.error(f"MultiClientStreamer stream error: {e}", exc_info=True)
#             try:
#                 ffmpeg_clean.kill()
#             except Exception:
#                 pass

#         finally:
#             # cleanup pipes
#             try:
#                 if ffmpeg_clean.stdout:
#                     ffmpeg_clean.stdout.close()
#             except Exception:
#                 pass
#             try:
#                 if ffmpeg_clean.stdin:
#                     ffmpeg_clean.stdin.close()
#             except Exception:
#                 pass


# TGLive/helpers/multi_client_streamer.py
import asyncio
from typing import AsyncGenerator
from TGLive.logger import LOGGER
from TGLive.helpers.bot import work_loads
from TGLive.helpers.byte_streamer import ByteStreamer


class MultiClientStreamer:
    """
    Converts Telegram file bytes -> MPEG-TS (ffmpeg) and yields TS chunks.
    Caller should feed these TS chunks into a single long-running HLS ffmpeg stdin.
    This version:
      - selects Hindi audio if present (multiple metadata forms)
      - falls back to common track indices if metadata missing
      - transcodes audio to AAC and copies video
    """

    def __init__(self, byte_streamer: ByteStreamer):
        self.bs = byte_streamer

    def _choose_least_loaded_index(self) -> int:
        if not work_loads:
            return 0
        return min(work_loads.keys(), key=lambda k: work_loads.get(k, 0))

    async def _pump_raw_to_ffmpeg(self, ffmpeg_proc, file_id, index, start_offset, part_count):
        """
        Pumps raw telegram chunks into ffmpeg's stdin (pipe:0).
        Runs as a background task so we can read ffmpeg stdout concurrently.
        """
        try:
            async for chunk in self.bs.yield_file(
                file_id=file_id,
                index=index,
                offset=start_offset,
                chunk_size=512 * 1024,
                part_count=part_count,
            ):
                if not chunk:
                    continue
                try:
                    ffmpeg_proc.stdin.write(chunk)
                    await ffmpeg_proc.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    LOGGER.warning("ffmpeg_clean stdin broken while pumping raw bytes.")
                    break
        except Exception as e:
            LOGGER.error(f"Error pumping raw bytes to ffmpeg_clean: {e}", exc_info=True)
        finally:
            # Close ffmpeg stdin to signal end-of-file for this input file
            try:
                if ffmpeg_proc.stdin:
                    ffmpeg_proc.stdin.close()
            except Exception:
                pass

    async def _read_and_log_stderr(self, proc, prefix="ffmpeg_clean"):
        """Background reader for ffmpeg stderr to capture errors/warnings."""
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode(errors="ignore").strip()
                if text:
                    LOGGER.warning(f"{prefix} stderr: {text}")
        except Exception:
            pass

    async def stream_video(self, chat_id: int, message_id: int, start_offset: int = 0) -> AsyncGenerator[bytes, None]:
        """
        Yields MPEG-TS chunks converted from the Telegram file.
        This runs ffmpeg per-file to convert container -> mpegts, but yields TS to be concatenated.
        """
        # 1. Get file properties (cached)
        file_info = await self.bs.get_file_properties(chat_id, message_id)

        # compute part_count safely
        file_size = getattr(file_info, "file_size", 0) or 0
        part_count = (file_size // (512 * 1024)) + 1 if file_size else 1

        index = self._choose_least_loaded_index()

        LOGGER.info(
            f"MultiClientStreamer: streaming message={message_id} size={file_size} bytes using client_index={index} (parts={part_count})"
        )

        # prepare mapping args:
        # 1) try Hindi metadata variants
        # 2) fallback to common track indices (2,1,0)
        mapping = [
            "-map", "0:v:0",

            # Try common Hindi metadata variants (optional maps)
            "-map", "0:a:m:language:hin?",
            "-map", "0:a:m:language:hi?",
            "-map", "0:a:m:language:hindi?",

            # Fallbacks by index (optional)
            "-map", "0:a:2?",
            "-map", "0:a:1?",
            "-map", "0:a:0?",
        ]

        # Start ffmpeg that converts incoming raw container bytes -> mpegts
        ffmpeg_clean = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",                        # overwrite if needed (safe for pipe)
            "-loglevel", "error",
            "-fflags", "+genpts",
            "-i", "pipe:0",              # input from stdin (raw telegram bytes)
            *mapping,
            "-c:v", "copy",
            "-c:a", "aac",               # transcode audio to AAC for HLS compatibility
            "-b:a", "128k",
            "-ac", "2",
            "-f", "mpegts",              # important: output mpegts for concatenation
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Start background pump of raw TG bytes into ffmpeg_clean.stdin
        pump_task = asyncio.create_task(
            self._pump_raw_to_ffmpeg(ffmpeg_clean, file_info, index, start_offset, part_count)
        )

        # Start background stderr logger for ffmpeg_clean
        asyncio.create_task(self._read_and_log_stderr(ffmpeg_clean, prefix="ffmpeg_clean"))

        # Read ffmpeg_clean stdout (TS packets) and yield to caller
        try:
            # Read in reasonable chunks (multiple of TS packet 188 recommended)
            READ_SIZE = 188 * 64  # ~12032 bytes; tune if you want larger/smaller
            while True:
                data = await ffmpeg_clean.stdout.read(READ_SIZE)
                if not data:
                    break
                yield data

            # Wait for pump to finish (it closes stdin when done)
            await pump_task
            # Ensure ffmpeg exits
            try:
                await ffmpeg_clean.wait()
            except Exception:
                pass

        except asyncio.CancelledError:
            LOGGER.info("MultiClientStreamer stream_video cancelled; terminating ffmpeg_clean.")
            try:
                ffmpeg_clean.kill()
            except Exception:
                pass
            raise

        except Exception as e:
            LOGGER.error(f"MultiClientStreamer stream error: {e}", exc_info=True)
            try:
                ffmpeg_clean.kill()
            except Exception:
                pass

        finally:
            # cleanup pipes
            try:
                if ffmpeg_clean.stdout:
                    ffmpeg_clean.stdout.close()
            except Exception:
                pass
            try:
                if ffmpeg_clean.stdin:
                    ffmpeg_clean.stdin.close()
            except Exception:
                pass
