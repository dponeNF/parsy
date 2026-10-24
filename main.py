from __future__ import annotations

import argparse
import atexit
import base64
import ctypes
import html
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any

import updater

APP_NAME = "Parsy"
APP_VERSION = "1.1.0"
SERVER_FLAG = "--streamlit-server"
IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0
ERROR_ALREADY_EXISTS = 183
SERVER_START_TIMEOUT = 60.0

_SHUTDOWN = threading.Event()
_SERVER_PROC: subprocess.Popen[bytes] | None = None
_SERVER_LOG_HANDLE: Any = None
_SERVER_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()
_MUTEX_HANDLE: Any = None


class StartupCancelled(Exception):
    pass


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _app_script() -> Path:
    root = _resource_root()
    candidate = root / "app.py"
    if candidate.exists():
        return candidate
    return Path(sys.executable).resolve().parent / "app.py"


def _asset(name: str) -> Path:
    return _resource_root() / "assets" / name


def _data_root() -> Path:
    override = os.environ.get("PARSY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME
    return Path.home() / ".parsy"


def _ensure_data_dirs() -> Path:
    root = _data_root()
    try:
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "webview2").mkdir(parents=True, exist_ok=True)
    except OSError:
        root = Path(os.environ.get("TEMP", ".")) / APP_NAME
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "webview2").mkdir(parents=True, exist_ok=True)
        os.environ["PARSY_DATA_DIR"] = str(root)
    return root


def _log_dir() -> Path:
    return _data_root() / "logs"


def _webview_storage() -> Path:
    return _data_root() / "webview2"


def _gui_log(message: str) -> None:
    try:
        path = _log_dir() / "gui.log"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(f"[{stamp}] {message.rstrip()}\n")
    except Exception:
        pass


def _apply_environment() -> None:
    values = {
        "STREAMLIT_SERVER_ADDRESS": "127.0.0.1",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
        "STREAMLIT_SERVER_RUN_ON_SAVE": "false",
        "STREAMLIT_SERVER_MAX_UPLOAD_SIZE": "500",
        "STREAMLIT_SERVER_MAX_MESSAGE_SIZE": "500",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "STREAMLIT_GLOBAL_DEVELOPMENT_MODE": "false",
        "STREAMLIT_CLIENT_TOOLBAR_MODE": "minimal",
        "STREAMLIT_THEME_BASE": "dark",
        "STREAMLIT_THEME_BACKGROUND_COLOR": "#0A0B0C",
        "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR": "#131416",
        "STREAMLIT_THEME_TEXT_COLOR": "#EDEAE3",
        "STREAMLIT_THEME_PRIMARY_COLOR": "#C2A878",
    }
    for key, value in values.items():
        os.environ[key] = value
    os.environ["PARSY_APP_VERSION"] = APP_VERSION
    os.environ["PARSY_INSTALLED"] = "1" if updater.is_installed() else "0"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_command(port: int) -> list[str]:
    app = str(_app_script())
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            SERVER_FLAG,
            "--app",
            app,
            "--port",
            str(port),
        ]
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app,
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--server.runOnSave",
        "false",
        "--server.maxUploadSize",
        "500",
        "--server.maxMessageSize",
        "500",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
        "--client.toolbarMode",
        "minimal",
    ]


def _prepare_server_log() -> Path:
    _log_dir().mkdir(parents=True, exist_ok=True)
    path = _log_dir() / "server.log"
    path.write_text("", encoding="utf-8")
    return path


def _start_server(port: int) -> subprocess.Popen[bytes]:
    global _SERVER_LOG_HANDLE
    log_path = _log_dir() / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8", errors="replace", buffering=1)
    handle.write(
        f"\n--- Parsy {APP_VERSION} | 127.0.0.1:{port} | "
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
    )
    handle.flush()
    with _SERVER_LOCK:
        if _SERVER_LOG_HANDLE is not None:
            try:
                _SERVER_LOG_HANDLE.close()
            except Exception:
                pass
        _SERVER_LOG_HANDLE = handle
    env = os.environ.copy()
    env["PARSY_LOG_PATH"] = str(log_path)
    env["PYTHONUNBUFFERED"] = "1"
    try:
        return subprocess.Popen(
            _server_command(port),
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            close_fds=True,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        handle.close()
        raise


def _wait_for_server(
    port: int,
    provider: subprocess.Popen[bytes],
    timeout: float = SERVER_START_TIMEOUT,
) -> None:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _SHUTDOWN.is_set():
            raise StartupCancelled()
        exit_code = provider.poll()
        if exit_code is not None:
            raise RuntimeError(f"Локальный сервер завершился с кодом {exit_code}.")
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError("Локальный сервер не запустился за 60 секунд.")


def _terminate_process(provider: subprocess.Popen[bytes] | None) -> None:
    if provider is None:
        return
    if provider.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(provider.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=10,
                check=False,
            )
        else:
            provider.terminate()
    except Exception:
        try:
            provider.kill()
        except Exception:
            pass


def _shutdown_server() -> None:
    global _SERVER_PROC, _SERVER_LOG_HANDLE
    with _SERVER_LOCK:
        provider = _SERVER_PROC
        _SERVER_PROC = None
    _terminate_process(provider)
    with _SERVER_LOCK:
        if _SERVER_LOG_HANDLE is not None:
            try:
                _SERVER_LOG_HANDLE.flush()
                _SERVER_LOG_HANDLE.close()
            except Exception:
                pass
            _SERVER_LOG_HANDLE = None


def _stop_attempt(provider: subprocess.Popen[bytes]) -> None:
    global _SERVER_PROC
    with _SERVER_LOCK:
        if _SERVER_PROC is provider:
            _SERVER_PROC = None
    _terminate_process(provider)


def _server_log_tail(limit: int = 4000) -> str:
    path = _log_dir() / "server.log"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-limit:].strip()


def _logo_data_uri() -> str:
    path = _asset("parsy.png")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


def _splash_html() -> str:
    logo = _logo_data_uri()
    logo_tag = (
        f'<img class="logo" src="{logo}" alt="Parsy">'
        if logo
        else '<div class="logo logo-fallback">P</div>'
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{APP_NAME}</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{
  display: flex; align-items: center; justify-content: center;
  background: #0A0B0C; color: #EDEAE3;
  font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
  -webkit-font-smoothing: antialiased; overflow: hidden;
}}
.splash {{ width: min(540px, 82vw); text-align: center; transform: translateY(-2vh); }}
.logo {{
  width: 78px; height: 78px; border-radius: 18px; display: inline-block;
  box-shadow: 0 18px 50px rgba(0,0,0,.42);
}}
.logo-fallback {{
  display: flex; align-items: center; justify-content: center;
  border: 1px solid #3B3C40; background: #121315; color: #C2A878;
  font-size: 34px; font-weight: 650;
}}
.eyebrow {{
  margin-top: 26px; color: #8C8982; font-size: 10px; font-weight: 650;
  letter-spacing: .2em; text-transform: uppercase;
}}
h1 {{
  margin: 13px 0 10px; font-size: clamp(32px, 4.2vw, 46px);
  font-weight: 650; letter-spacing: -.045em; line-height: 1.05;
}}
p {{ margin: 0; color: #A5A29B; font-size: 13px; line-height: 1.7; }}
.track {{
  width: min(280px, 70%); height: 2px; margin: 34px auto 0;
  background: #202125; border-radius: 2px; overflow: hidden;
}}
.track::after {{
  content: ""; display: block; width: 36%; height: 100%; background: #C2A878;
  animation: slide 1.35s ease-in-out infinite;
}}
.hint {{ margin-top: 15px; color: #5E5C57; font-size: 10.5px; letter-spacing: .04em; }}
@keyframes slide {{
  0% {{ transform: translateX(-105%); }}
  100% {{ transform: translateX(315%); }}
}}
</style>
</head>
<body>
  <main class="splash">
    {logo_tag}
    <div class="eyebrow">PARSY / DEMO INTELLIGENCE</div>
    <h1>Запускаем Parsy</h1>
    <p>Поднимаем локальный движок анализа демок.<br>Это занимает несколько секунд.</p>
    <div class="track"></div>
    <div class="hint">v{APP_VERSION} · всё считается на этом компьютере</div>
  </main>
</body>
</html>"""


def _error_html(error: str, log_tail: str) -> str:
    safe_error = html.escape(error or "Неизвестная ошибка.")
    safe_tail = html.escape(log_tail or "Лог сервера пуст.")
    log_path = html.escape(str(_log_dir()))
    logo = _logo_data_uri()
    logo_tag = (
        f'<img class="logo" src="{logo}" alt="Parsy">'
        if logo
        else '<div class="logo logo-fallback">P</div>'
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{APP_NAME}</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ min-height: 100%; margin: 0; }}
body {{
  background: #0A0B0C; color: #EDEAE3; padding: 44px;
  font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ width: min(820px, 100%); margin: 0 auto; }}
.logo {{ width: 56px; height: 56px; border-radius: 13px; }}
.logo-fallback {{
  display: flex; align-items: center; justify-content: center;
  border: 1px solid #3B3C40; background: #121315; color: #C2A878;
  font-size: 24px; font-weight: 650;
}}
.eyebrow {{
  margin-top: 22px; color: #8C8982; font-size: 10px; font-weight: 650;
  letter-spacing: .2em; text-transform: uppercase;
}}
h1 {{ margin: 12px 0 12px; font-size: 34px; letter-spacing: -.04em; }}
p {{ color: #A5A29B; font-size: 13px; line-height: 1.7; }}
.box {{
  margin-top: 22px; padding: 18px 20px; border: 1px solid #2A2B2F;
  border-radius: 10px; background: #121315;
}}
.box strong {{ display: block; margin-bottom: 8px; font-size: 12px; }}
pre {{
  margin: 0; color: #8F8C85; font-size: 11px; line-height: 1.55;
  white-space: pre-wrap; word-break: break-word; max-height: 230px; overflow: auto;
}}
.actions {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
button {{
  border: 1px solid #34353A; border-radius: 8px; padding: 10px 15px;
  background: #E9E4D8; color: #111214; font: inherit; font-size: 12px;
  font-weight: 650; cursor: pointer;
}}
.note {{ margin-top: 18px; color: #6F6D68; font-size: 11px; line-height: 1.6; }}
</style>
</head>
<body>
  <main class="wrap">
    {logo_tag}
    <div class="eyebrow">PARSY / STARTUP ERROR</div>
    <h1>Не удалось запустить Parsy</h1>
    <p>{safe_error}</p>
    <div class="box">
      <strong>Технический лог</strong>
      <pre>{safe_tail}</pre>
    </div>
    <div class="actions">
      <button onclick="pywebview.api.open_logs()">Открыть папку логов</button>
    </div>
    <div class="note">Логи: {log_path}</div>
  </main>
</body>
</html>"""


class DesktopApi:
    def open_logs(self) -> None:
        try:
            os.startfile(str(_log_dir()))
        except Exception:
            _gui_log(traceback.format_exc())


def _boot(window: Any, stop_event: threading.Event) -> None:
    global _SERVER_PROC
    _prepare_server_log()
    last_error = ""
    for _ in range(2):
        if stop_event.is_set():
            return
        port = _free_port()
        try:
            provider = _start_server(port)
        except Exception:
            last_error = traceback.format_exc()
            _gui_log(last_error)
            continue
        with _SERVER_LOCK:
            _SERVER_PROC = provider
        try:
            _wait_for_server(port, provider)
        except StartupCancelled:
            _stop_attempt(provider)
            return
        except Exception as error:
            last_error = str(error)
            _gui_log(f"startup attempt failed: {error}")
            _stop_attempt(provider)
            continue
        if stop_event.is_set():
            _stop_attempt(provider)
            return
        try:
            window.load_url(f"http://127.0.0.1:{port}")
            window.set_title(APP_NAME)
        except Exception:
            last_error = traceback.format_exc()
            _gui_log(last_error)
            _stop_attempt(provider)
            continue
        return
    if not stop_event.is_set():
        try:
            window.load_html(_error_html(last_error, _server_log_tail()))
        except Exception:
            _gui_log(traceback.format_exc())


def _window_size() -> tuple[int, int]:
    if not IS_WINDOWS:
        return 1440, 940
    try:
        user32 = ctypes.windll.user32
        screen_width = int(user32.GetSystemMetrics(0))
        screen_height = int(user32.GetSystemMetrics(1))
        width = min(1440, max(1024, screen_width - 80))
        height = min(940, max(680, screen_height - 100))
        return width, height
    except Exception:
        return 1440, 940


def _webview2_available() -> bool:
    if not IS_WINDOWS:
        return True
    roots = [
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for value in roots:
        if not value:
            continue
        app_dir = Path(value) / "Microsoft" / "EdgeWebView" / "Application"
        if app_dir.is_dir() and any(app_dir.glob("*/msedgewebview2.exe")):
            return True
    return False


def _set_app_user_model_id() -> None:
    if not IS_WINDOWS:
        return
    try:
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        setter("Parsy.Desktop.1")
    except Exception:
        pass


def _single_instance_available() -> bool:
    global _MUTEX_HANDLE
    if not IS_WINDOWS:
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p,
    ]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "Local\\ParsyDesktopApp")
    if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
        return True
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow.restype = ctypes.c_bool
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.restype = ctypes.c_bool
    handle = user32.FindWindowW(None, APP_NAME)
    if handle:
        user32.ShowWindow(handle, 9)
        user32.SetForegroundWindow(handle)
    else:
        _message_box("Parsy уже запущен.", APP_NAME)
    return False


def _message_box(message: str, title: str = APP_NAME) -> None:
    try:
        if IS_WINDOWS:
            user32 = ctypes.windll.user32
            user32.MessageBoxW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_uint,
            ]
            user32.MessageBoxW.restype = ctypes.c_int
            user32.MessageBoxW(None, message, title, 0x00000010)
        else:
            print(f"{title}: {message}", file=sys.stderr)
    except Exception:
        pass


def _on_window_closed() -> None:
    _gui_log("window closed")
    _SHUTDOWN.set()
    _shutdown_server()


def _parse_child_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(SERVER_FLAG, action="store_true", dest="server")
    parser.add_argument("--app")
    parser.add_argument("--port", type=int)
    return parser.parse_known_args()[0]


def _ensure_child_streams() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = os.environ.get("PARSY_LOG_PATH")
    if log_path:
        stream = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
    else:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _run_streamlit_server() -> int:
    args = _parse_child_args()
    if not args.app or not args.port:
        return 2
    _apply_environment()
    _ensure_data_dirs()
    _ensure_child_streams()
    app_path = Path(args.app)
    if not app_path.is_file():
        print(f"Parsy: app script not found: {app_path}", file=sys.stderr)
        return 3
    try:
        from streamlit.web import cli as streamlit_cli
    except Exception:
        traceback.print_exc()
        return 4
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--server.runOnSave",
        "false",
        "--server.maxUploadSize",
        "500",
        "--server.maxMessageSize",
        "500",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
        "--client.toolbarMode",
        "minimal",
    ]
    try:
        result = streamlit_cli.main()
        return int(result) if isinstance(result, int) else 0
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 0
    except Exception:
        traceback.print_exc()
        return 5


def _watch_update_requests(window: Any, stop_event: threading.Event) -> None:
    if not getattr(sys, "frozen", False) or not updater.is_installed():
        return
    while not stop_event.wait(2.0):
        request = updater.read_update_request()
        if not request:
            continue
        try:
            version = str(request.get("version") or "")
            if not updater.is_newer(version, APP_VERSION):
                updater.clear_update_request()
                continue
            installer = updater.validate_request(request)
            updater.launch_update(installer, updater.installed_app_exe(), os.getpid())
            _gui_log(f"update requested: {version} -> {installer}")
            updater.clear_update_request()
            stop_event.set()
            try:
                window.destroy()
            except Exception:
                _gui_log(traceback.format_exc())
                _shutdown_server()
                os._exit(0)
            return
        except Exception:
            _gui_log(traceback.format_exc())
            updater.clear_update_request()


def _run_desktop() -> int:
    _apply_environment()
    _ensure_data_dirs()
    _set_app_user_model_id()
    _gui_log(f"startup v{APP_VERSION}")
    if not _single_instance_available():
        return 0
    if not _webview2_available():
        _message_box(
            "Не найден Microsoft Edge WebView2 Runtime.\n\n"
            "Установите его и запустите Parsy снова. Установщик Parsy Setup "
            "ставит этот компонент автоматически.\n\n"
            "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
        )
        return 1
    try:
        import webview
    except Exception:
        error = traceback.format_exc()
        _gui_log(error)
        _message_box(
            "Не удалось загрузить компонент окна pywebview.\n"
            "Переустановите Parsy или запустите build.ps1 заново."
        )
        return 1
    width, height = _window_size()
    icon = _asset("parsy.ico")
    try:
        window = webview.create_window(
            APP_NAME,
            html=_splash_html(),
            js_api=DesktopApi(),
            width=width,
            height=height,
            min_size=(1024, 680),
            background_color="#0A0B0C",
            text_select=True,
            confirm_close=False,
        )
        if window is None:
            raise RuntimeError("pywebview не создал окно приложения.")
        window.events.closed += _on_window_closed
        threading.Thread(
            target=_watch_update_requests,
            args=(window, _SHUTDOWN),
            daemon=True,
            name="parsy-updater",
        ).start()
        webview.start(
            _boot,
            args=(window, _SHUTDOWN),
            private_mode=False,
            storage_path=str(_webview_storage()),
            icon=str(icon) if icon.exists() else None,
            debug=False,
        )
    except Exception:
        error = traceback.format_exc()
        _gui_log(error)
        _message_box(
            "Не удалось открыть окно Parsy.\n\n"
            f"Лог: {_log_dir() / 'gui.log'}"
        )
        return 1
    finally:
        _SHUTDOWN.set()
        _shutdown_server()
    return 0


def main() -> int:
    if IS_WINDOWS:
        try:
            ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
        except Exception:
            pass
    if SERVER_FLAG in sys.argv:
        return _run_streamlit_server()
    return _run_desktop()


if __name__ == "__main__":
    atexit.register(_shutdown_server)
    raise SystemExit(main())
