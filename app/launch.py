"""Start the local model service, warm the model, and run Study Buddy."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import settings


def ollama_request(path, payload=None, timeout=5):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(settings.ollama_url.rstrip("/") + path, data=body,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def service_ready():
    try:
        ollama_request("/api/tags")
        return True
    except (URLError, OSError, ValueError):
        return False


def has_model(models, wanted):
    normalized = wanted if ":" in wanted else wanted + ":latest"
    return any(item.get("name") in {wanted, normalized} for item in models)


def stop_owned(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    arguments = sys.argv[1:]
    if "--help" in arguments or "--version" in arguments:
        return subprocess.call([sys.executable, "-m", "uvicorn", *arguments])
    missing = [name for name in ("uvicorn", "fastapi", "httpx", "pptx", "bs4") if importlib.util.find_spec(name) is None]
    if missing:
        print("Missing app dependencies. Run: python3 -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    port = int(os.environ.get("BUDDY_PORT", "8000"))
    # Avoid loading a model only to discover that another app already owns the port.
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        print(f"Port {port} is already in use. Stop the existing server or set BUDDY_PORT to another port.", file=sys.stderr)
        return 1
    daemon = None
    server = None
    log = None
    try:
        if not service_ready():
            url = urlsplit(settings.ollama_url)
            if url.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise RuntimeError("The configured Ollama server is unreachable; start it on its host first.")
            executable = shutil.which("ollama")
            if executable is None:
                raise RuntimeError("Install Ollama first from https://ollama.com/download, then run study buddy again.")
            log_dir = settings.data_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "ollama.log"
            log = log_path.open("a")
            environment = os.environ.copy()
            environment["OLLAMA_HOST"] = url.netloc
            print("Starting Ollama...", flush=True)
            daemon = subprocess.Popen([executable, "serve"], env=environment, stdout=log, stderr=log)
            deadline = time.monotonic() + 45
            while not service_ready():
                if daemon.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(f"Ollama did not start. See {log_path.resolve()}")
                time.sleep(.5)
        else:
            print("Using the running Ollama service.", flush=True)
        model = settings.ollama_model
        if not has_model(ollama_request("/api/tags").get("models", []), model):
            print(f"Downloading {model} for first use. This may take several minutes...", flush=True)
            result = ollama_request("/api/pull", {"model": model, "stream": False}, timeout=3600)
            if result.get("error"):
                raise RuntimeError(result["error"])
        print(f"Loading Professor ({model})...", flush=True)
        result = ollama_request("/api/generate", {"model": model, "stream": False, "keep_alive": "30m"}, timeout=300)
        if result.get("error"):
            raise RuntimeError(result["error"])
        print(f"Professor is loaded. Open http://127.0.0.1:{port}\nPress Ctrl+C to stop Study Buddy.", flush=True)
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                   "--host", "127.0.0.1", "--port", str(port), *arguments])
        return server.wait()
    except KeyboardInterrupt:
        print("\nStopping Study Buddy.", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Study Buddy could not start: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_owned(server)
        stop_owned(daemon)
        if log:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
