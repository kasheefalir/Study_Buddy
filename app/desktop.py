"""Desktop entry point; does not change the source-checkout launcher."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import socket
import sys
import threading
import webbrowser


def data_directory():
    override = os.environ.get("BUDDY_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Study Buddy" / "data"


def bind_socket():
    """Reserve a loopback port before starting the server, avoiding a port race."""
    for port in (8000, 8001, 8002, 8003, 8004, 0):
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(128)
            return sock
        except OSError:
            sock.close()
    raise RuntimeError("Could not reserve a local address.")


def main():
    # Set paths before any app modules import their Settings singleton.
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["BUDDY_DATA_DIR"] = str(directory)
    logs = directory / "logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(filename=logs / "desktop.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if "--smoke-test" in sys.argv:
        # Exercise frozen imports and packaged resources without Ollama or a GUI.
        import asyncio
        import httpx
        from app.main import app, static_dir, tileset_dir

        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://test") as client:
                for path in ("/", "/static/app.js", "/static/styles.css"):
                    response = await client.get(path)
                    assert response.status_code == 200, path
            assert (static_dir / "index.html").is_file()
            assert (tileset_dir / "tilest.png").is_file()
        try:
            asyncio.run(check())
        except Exception:
            logging.exception("Packaged smoke test failed")
            raise SystemExit(1)
        return
    import tkinter as tk
    from tkinter import messagebox, ttk
    root = tk.Tk()
    root.title("Study Buddy")
    root.geometry("490x300")
    root.minsize(440, 280)
    lock = None
    if sys.platform == "win32":
        import msvcrt
        lock = (directory / "desktop.lock").open("a+b")
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            messagebox.showinfo("Study Buddy", "Study Buddy is already open. Use its launcher window to open the classroom.")
            lock.close()
            root.destroy()
            return
    status = tk.StringVar(value="Starting your classroom...")
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Study Buddy", font=("Segoe UI", 22)).pack(anchor="w")
    ttk.Label(frame, textvariable=status, wraplength=420).pack(anchor="w", pady=16)
    classroom = ttk.Button(frame, text="Open classroom", state="disabled")
    classroom.pack(fill="x", pady=4)
    ttk.Button(frame, text="Get Ollama desktop app",
               command=lambda: webbrowser.open("https://ollama.com/download/windows")).pack(fill="x", pady=4)
    ttk.Label(frame, text="Open Ollama, then choose or download a model in the classroom.",
              wraplength=420).pack(anchor="w", pady=8)
    server = None
    sock = None
    worker = None

    def quit_app():
        if server:
            server.should_exit = True
        status.set("Closing Study Buddy...")
        classroom.configure(state="disabled")
        quit_button.configure(state="disabled")
        wait_for_shutdown()

    def wait_for_shutdown():
        if worker and worker.is_alive():
            root.after(100, wait_for_shutdown)
        else:
            if sock:
                sock.close()
            if lock:
                lock.close()
            root.destroy()

    quit_button = ttk.Button(frame, text="Quit Study Buddy", command=quit_app)
    quit_button.pack(fill="x", pady=4)
    root.protocol("WM_DELETE_WINDOW", quit_app)
    try:
        import uvicorn
        from app.main import app
        sock = bind_socket()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, loop="asyncio",
                                http="h11", ws="none", timeout_graceful_shutdown=5))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()

        def check_started():
            if server.should_exit:
                return
            if server.started and worker.is_alive():
                status.set(f"Classroom is open at {url}\nKeep this window open while studying.")
                classroom.configure(state="normal", command=lambda: webbrowser.open(url))
                webbrowser.open(url)
            elif worker.is_alive():
                root.after(150, check_started)
            else:
                status.set(f"Couldn't start. Details are in {logs / 'desktop.log'}")

        root.after(150, check_started)
    except Exception:
        logging.exception("Desktop startup failed")
        status.set(f"Couldn't start. Details are in {logs / 'desktop.log'}")
    root.mainloop()


if __name__ == "__main__":
    main()
