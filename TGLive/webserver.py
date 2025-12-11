import os
import asyncio
import aiohttp
from aiohttp import web
from TGLive.logger import LOGGER


async def status_page(request):
    return web.Response(text="TgLive Streaming Server is Running")


async def handle_hls(request):
    filename = request.match_info.get("filename")

    if ".." in filename or filename.startswith("/"):
        return web.Response(status=400, text="Invalid filename")

    file_path = os.path.join("hls", filename)

    if not os.path.exists(file_path):
        return web.Response(status=404, text="File not found")

    if filename.endswith(".m3u8"):
        return web.FileResponse(file_path, headers={"Content-Type": "application/x-mpegURL"})
    elif filename.endswith(".ts"):
        return web.FileResponse(file_path, headers={"Content-Type": "video/mp2t"})
    else:
        return web.FileResponse(file_path)


async def list_all_files(request):
    root_dir = "."  # change to "/" if you want to expose the ENTIRE server (VERY dangerous)

    file_tree = []

    for folder, subfolders, files in os.walk(root_dir):
        for name in files:
            full_path = os.path.join(folder, name)
            file_tree.append(full_path)

    # Simple text output
    return web.Response(text="\n".join(file_tree))

async def file_browser(request):
    root_dir = "/"    # ⚠ full system access — change to "." if you want only project folder
    path = request.query.get("path", root_dir)

    # Security checks
    if ".." in path:
        return web.Response(status=400, text="Invalid path")

    # If path is a file → return file
    if os.path.isfile(path):
        return web.FileResponse(path)

    # If path is a directory → list content
    if os.path.isdir(path):
        items = os.listdir(path)
        items.sort()

        html = "<h2>File Browser</h2>"
        html += f"<p>Current path: {path}</p><ul>"

        # Parent directory
        parent = os.path.dirname(path.rstrip("/"))
        html += f'<li><a href="/explorer?path={parent}">.. (parent)</a></li>'

        # List directories & files
        for item in items:
            full = os.path.join(path, item)
            html += f'<li><a href="/explorer?path={full}">{item}</a></li>'

        html += "</ul>"
        return web.Response(text=html, content_type="text/html")

    return web.Response(status=404, text="Not found")


async def stream_logs(request):
    log_file = "log.txt"

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

    await response.prepare(request)

    try:
        f = open(log_file, "r", errors="ignore")
        f.seek(0)
    except FileNotFoundError:
        await response.write(b"data: log.txt not found\n\n")
        await response.write_eof()
        return response

    try:
        while True:
            line = f.readline()
            if line:
                try:
                    await response.write(line.encode("utf-8"))
                except (ConnectionResetError, aiohttp.ClientConnectionResetError):
                    break
            else:
                await asyncio.sleep(0.3)
    finally:
        f.close()

    return response


@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def create_app():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", status_page)
    app.router.add_get("/hls/{filename}", handle_hls)
    app.router.add_get("/live-logs", stream_logs)
    # app.router.add_get("/all-files", list_all_files)
    app.router.add_get("/explorer", file_browser)

    return app


async def start_server(port=8000):
    app = create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    LOGGER.info(f"Web server started on port {port}")
    return runner
