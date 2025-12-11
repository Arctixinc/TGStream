import asyncio
import logging
import os
from traceback import format_exc

from pyrogram import idle

from TGLive import __version__
from TGLive.logger import LOGGER
from TGLive.helpers.bot import LiveBot, Helper, multi_clients
from TGLive.helpers.multi_client import initialize_clients
from TGLive.helpers.video_playlist import VideoPlaylistManager
from TGLive.helpers.multi_client_streamer import MultiClientStreamer
from TGLive.helpers.playlist_manager import PlaylistStreamGenerator
from TGLive.webserver import start_server
from TGLive.config import Telegram
from TGLive.helpers.byte_streamer import ByteStreamer

# ======================================================
# START ALL SERVICES
# ======================================================
async def start_services():
    ffmpeg_hls = None
    stream_task = None
    web_runner = None

    try:
        LOGGER.info(f"Starting TgLive v{__version__}")
        await asyncio.sleep(1)

        # --------------------------
        # Start LiveBot
        # --------------------------
        await LiveBot.start()
        try:
            LiveBot.username = (await LiveBot.get_me()).username
            LOGGER.info(f"LiveBot Started as @{LiveBot.username}")
        except Exception:
            LOGGER.warning("Could not fetch LiveBot username.")
        await asyncio.sleep(1)

        # --------------------------
        # Start HelperBot
        # --------------------------
        await Helper.start()
        try:
            Helper.username = (await Helper.get_me()).username
            LOGGER.info(f"HelperBot Started as @{Helper.username}")
        except Exception:
            LOGGER.warning("Could not fetch HelperBot username.")
        await asyncio.sleep(1)

        # --------------------------
        # Initialize Multi Clients
        # --------------------------
        LOGGER.info("Initializing Multi Clients...")
        await initialize_clients()
        await asyncio.sleep(2)

        # --------------------------
        # Start Web Server
        # --------------------------
        import os
        PORT = int(os.environ.get("PORT", 8000))
        web_runner = await start_server(port=PORT)


        LOGGER.info(f"Web Server Started at http://0.0.0.0:{PORT}/hls/live.m3u8")

        # --------------------------
        # Configure Playlist
        # --------------------------
        vp = VideoPlaylistManager(Helper, chat_id=Telegram.CHANNEL_ID)
        await vp.build_initial_playlist()
        LOGGER.info("Playlist Manager started.")
        LOGGER.info(await vp.get_playlist())

        bs = ByteStreamer(Helper)
        ms = MultiClientStreamer(bs)
        pg = PlaylistStreamGenerator(vp, ms)

        os.makedirs("hls", exist_ok=True)

        # Single long-running HLS ffmpeg: accepts MPEG-TS on stdin
        # ffmpeg_hls = await asyncio.create_subprocess_exec(
        #     "ffmpeg",
        #     "-re",
        #     "-loglevel", "error",
        #     "-i", "pipe:0",
        #     "-map", "0:v",
        #     "-map", "0:a?",
        #     "-c:v", "copy",
        #     "-c:a", "copy",
        #     "-f", "hls",
        #     "-hls_time", "4",
        #     "-hls_list_size", "6",
        #     "-hls_flags", "delete_segments+append_list+omit_endlist",
        #     "hls/live.m3u8",
        #     stdin=asyncio.subprocess.PIPE,
        #     stdout=asyncio.subprocess.DEVNULL,
        #     stderr=asyncio.subprocess.PIPE
        # )


        # ffmpeg_hls = await asyncio.create_subprocess_exec(
        #     "ffmpeg",
        #     "-re",
        #     "-loglevel", "error",
        #     "-i", "pipe:0",
        #     "-map", "0:v",
        #     "-map", "0:a?",
        #     "-c:v", "copy",
        #     "-c:a", "aac",
        #     "-b:a", "128k",
        #     "-ac", "2",
        #     "-f", "hls",
        #     "-hls_time", "4",
        #     "-hls_list_size", "6",
        #     "-hls_flags", "delete_segments+append_list+omit_endlist",
        #     "hls/live.m3u8",
        #     stdin=asyncio.subprocess.PIPE,
        #     stdout=asyncio.subprocess.DEVNULL,
        #     stderr=asyncio.subprocess.PIPE
        # )
        ffmpeg_hls = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-re",
            "-loglevel", "error",
            "-i", "pipe:0",

            # ---- CONSISTENT AUDIO TRACK SELECTION ----
            # Try Hindi first (metadata-based)
            "-map", "0:v:0",
            # "-map", "0:a:m:language:hin?",
            # "-map", "0:a:m:language:Hin?",
            # "-map", "0:a:m:language:hi?",
            # "-map", "0:a:m:language:hindi?",

            # Fallback to common Indian track ordering
            "-map", "0:a:2?",
            "-map", "0:a:1?",
            "-map", "0:a:0?",

            # ---- AUDIO TRANSCODING FOR UNIVERSAL HLS SUPPORT ----
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",

            # ---- HLS CONFIG ----
            "-f", "hls",
            "-hls_time", "4",
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments+append_list+omit_endlist",
            "hls/live.m3u8",

            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE
        )

        # ======================================================
        # STABILIZER TS injection (HLS clock warm-up)
        # ======================================================
        async def send_stabilizer():
            try:
                if not os.path.isfile("stabilizer.ts"):
                    LOGGER.error("stabilizer.ts missing — please generate it!")
                    return

                LOGGER.info("Injecting stabilizer.ts (HLS warm-up)...")

                with open("stabilizer.ts", "rb") as f:
                    data = f.read()

                if data and ffmpeg_hls and ffmpeg_hls.stdin:
                    ffmpeg_hls.stdin.write(data)
                    await ffmpeg_hls.stdin.drain()
                    LOGGER.info("Stabilizer TS injected successfully.")
                else:
                    LOGGER.error("stabilizer.ts is empty or ffmpeg not ready!")
            except Exception as e:
                LOGGER.error(f"Failed to inject stabilizer TS: {e}", exc_info=True)

        # Send stabilizer BEFORE any Telegram video chunks
        await send_stabilizer()
        LOGGER.info("HLS clock warm-up done. Starting Telegram stream...")

        # optional: log ffmpeg stderr in background (low-priority debug)
        async def _read_ffmpeg_stderr(proc):
            try:
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    LOGGER.debug(f"ffmpeg_hls: {line.decode(errors='ignore').strip()}")
            except Exception:
                pass

        if ffmpeg_hls:
            asyncio.create_task(_read_ffmpeg_stderr(ffmpeg_hls))

        # The runner: write TS chunks into ffmpeg_hls.stdin
        async def _run_stream():
            LOGGER.info("Stream Engine started.")
            total_bytes = 0
            chunks_written = 0

            try:
                async for ts_chunk in pg.generator():
                    if not ts_chunk:
                        continue

                    # ensure ffmpeg still alive
                    if ffmpeg_hls is None or ffmpeg_hls.returncode is not None:
                        LOGGER.error("ffmpeg_hls terminated or not available (returncode=%s).", getattr(ffmpeg_hls, "returncode", None))
                        break

                    try:
                        ffmpeg_hls.stdin.write(ts_chunk)
                        await ffmpeg_hls.stdin.drain()
                        chunks_written += 1
                        total_bytes += len(ts_chunk)

                        if chunks_written == 1 or chunks_written % 50 == 0:
                            LOGGER.info(f"Written to ffmpeg_hls: chunks={chunks_written} total_bytes={total_bytes}")
                    except BrokenPipeError:
                        LOGGER.error("BrokenPipe when writing to ffmpeg_hls; stopping stream runner.")
                        break
                    except Exception as e:
                        LOGGER.error(f"Error writing to ffmpeg_hls: {e}", exc_info=True)
                        break

            except asyncio.CancelledError:
                LOGGER.info("Stream runner cancelled.")
            except Exception as e:
                LOGGER.error(f"Stream runner crashed: {e}", exc_info=True)
            finally:
                # flush and close stdin to let ffmpeg finalize safely
                try:
                    if ffmpeg_hls and ffmpeg_hls.stdin:
                        ffmpeg_hls.stdin.close()
                except Exception:
                    pass
                LOGGER.info("Stream runner finished.")

        # Start streaming task
        stream_task = asyncio.create_task(_run_stream())

        # keep bots alive until process is interrupted
        await idle()

        LOGGER.warning("Idle ended — shutdown requested by user (idle returned).")

    except Exception as e:
        LOGGER.error(f"Error Starting TgLive Services: {e}", exc_info=True)
    finally:
        LOGGER.info("Cleaning up start_services resources...")

        # Cancel stream task
        if stream_task:
            stream_task.cancel()
            try:
                await stream_task
            except Exception:
                pass

        # Stop ffmpeg gracefully
        try:
            if ffmpeg_hls:
                # close stdin if open
                try:
                    if ffmpeg_hls.stdin:
                        ffmpeg_hls.stdin.close()
                except Exception:
                    pass

                # give ffmpeg a short time to finalize
                try:
                    await asyncio.wait_for(ffmpeg_hls.wait(), timeout=5)
                except asyncio.TimeoutError:
                    LOGGER.warning("ffmpeg did not exit in time; killing.")
                    try:
                        ffmpeg_hls.kill()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            LOGGER.exception("Error while shutting down ffmpeg_hls")

        # cleanup web runner
        if web_runner:
            try:
                await web_runner.cleanup()
            except Exception:
                LOGGER.exception("Failed to cleanup web runner")

        LOGGER.info("start_services cleanup complete.")

# ======================================================
# STOP ALL SERVICES
# ======================================================
async def stop_services():
    try:
        LOGGER.info("Stopping TgLive Services...")

        # ---------------------------------------
        # STOP MULTI-CLIENTS (skip client 0)
        # ---------------------------------------
        for cid, client in list(multi_clients.items()):
            if cid == 0:
                continue
            try:
                await client.stop()
                LOGGER.info(f"Multi-Client {cid} stopped successfully.")
            except Exception as e:
                LOGGER.error(f"Failed stopping Multi-Client {cid}: {e}")

        # ---------------------------------------
        # STOP LIVE BOT
        # ---------------------------------------
        try:
            await LiveBot.stop()
            LOGGER.info("LiveBot stopped successfully.")
        except Exception as e:
            LOGGER.warning(f"LiveBot stop may have failed or was already stopped: {e}")

        # ---------------------------------------
        # STOP HELPER BOT
        # ---------------------------------------
        try:
            await Helper.stop()
            LOGGER.info("HelperBot stopped successfully.")
        except Exception as e:
            LOGGER.warning(f"Helper stop may have failed or was already stopped: {e}")

        LOGGER.info("TgLive Services Stopped Successfully")

    except Exception as e:
        LOGGER.error(f"Error Stopping TgLive Services: {e}")
        LOGGER.error(format_exc())

# ======================================================
# MAIN ENTRY POINT
# ======================================================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(start_services())

    except KeyboardInterrupt:
        LOGGER.info("Shutdown Requested...")

    finally:
        # Ensure graceful stopping of TG clients and related resources
        try:
            loop.run_until_complete(stop_services())
        except Exception:
            LOGGER.exception("Error while running stop_services()")
        loop.stop()
        logging.shutdown()
