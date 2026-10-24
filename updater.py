from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

APP_NAME = "Parsy"
APP_ID = "{430557C9-5801-4534-A64A-24B655B0BE67}"
REPO = "dponeNF/parsy"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = "Parsy-Updater/1.0"
REQUEST_NAME = "update.request"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _data_root() -> Path:
    override = os.environ.get("PARSY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME
    return Path.home() / ".parsy"


def updates_dir() -> Path:
    path = _data_root() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def request_path() -> Path:
    return _data_root() / REQUEST_NAME


def parse_version(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().lstrip("vV")
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    left = parse_version(latest)
    right = parse_version(current)
    if not left or not right:
        return False
    length = max(len(left), len(right))
    left += (0,) * (length - len(left))
    right += (0,) * (length - len(right))
    return left > right


def _release_api() -> str:
    return os.environ.get("PARSY_UPDATE_API") or RELEASE_API


def check_latest(current_version: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        _release_api(),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GitHub вернул ошибку {error.code}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Не удалось проверить обновления: {error.reason}") from error
    except TimeoutError as error:
        raise RuntimeError("GitHub не ответил вовремя.") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("GitHub вернул неожиданный ответ.") from error

    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    version = tag.lstrip("vV")
    if not parse_version(version):
        raise RuntimeError("В релизе GitHub не найдена версия.")
    assets = data.get("assets") or []
    setup_asset = None
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.lower().startswith("parsy-setup-") and name.lower().endswith(".exe"):
            setup_asset = asset
            break
    if setup_asset is None:
        raise RuntimeError("В последнем релизе нет установщика Parsy-Setup-*.exe.")

    digest = str(setup_asset.get("digest") or "").strip().lower()
    sha256 = digest[7:] if digest.startswith("sha256:") else ""
    return {
        "version": version,
        "tag": tag,
        "name": str(data.get("name") or f"Parsy {version}"),
        "notes": str(data.get("body") or ""),
        "html_url": str(data.get("html_url") or ""),
        "published_at": str(data.get("published_at") or ""),
        "prerelease": bool(data.get("prerelease")),
        "is_newer": is_newer(version, current_version),
        "asset": {
            "name": str(setup_asset.get("name") or ""),
            "size": int(setup_asset.get("size") or 0),
            "url": str(setup_asset.get("browser_download_url") or ""),
            "sha256": sha256,
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cleanup_old(destination: Path) -> None:
    for item in updates_dir().glob("Parsy-Setup-*.exe"):
        if item.resolve() == destination.resolve():
            continue
        try:
            item.unlink()
        except OSError:
            pass


def download_installer(
    release: dict[str, Any],
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 60.0,
) -> Path:
    asset = release.get("asset") or {}
    url = str(asset.get("url") or "")
    name = str(asset.get("name") or "")
    expected_size = int(asset.get("size") or 0)
    expected_sha = str(asset.get("sha256") or "").lower()
    if not url or not name:
        raise RuntimeError("В релизе нет ссылки на установщик.")
    destination = updates_dir() / name
    if destination.is_file():
        size_ok = not expected_size or destination.stat().st_size == expected_size
        hash_ok = not expected_sha or sha256_file(destination) == expected_sha
        if size_ok and hash_ok:
            if progress:
                progress(destination.stat().st_size, destination.stat().st_size)
            return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        partial.unlink()
    except OSError:
        pass
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or expected_size or 0)
            done = 0
            with partial.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except urllib.error.HTTPError as error:
        try:
            partial.unlink()
        except OSError:
            pass
        raise RuntimeError(f"Не удалось скачать установщик: HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        try:
            partial.unlink()
        except OSError:
            pass
        raise RuntimeError(f"Не удалось скачать установщик: {error.reason}") from error
    except TimeoutError as error:
        try:
            partial.unlink()
        except OSError:
            pass
        raise RuntimeError("Скачивание установщика остановилось по таймауту.") from error

    actual_size = partial.stat().st_size
    if expected_size and actual_size != expected_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError("Размер скачанного установщика не совпал с релизом.")
    if expected_sha:
        actual_sha = sha256_file(partial)
        if actual_sha != expected_sha:
            partial.unlink(missing_ok=True)
            raise RuntimeError("SHA-256 скачанного установщика не совпал с релизом.")
    os.replace(partial, destination)
    _cleanup_old(destination)
    return destination


def write_update_request(installer: Path, version: str, sha256: str = "") -> Path:
    path = request_path()
    temporary = path.with_suffix(".tmp")
    payload = {
        "version": str(version),
        "installer": str(installer),
        "sha256": str(sha256 or (sha256_file(installer) if installer.is_file() else "")),
        "requested_at": time.time(),
    }
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def read_update_request() -> dict[str, Any] | None:
    path = request_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        clear_update_request()
        return None
    return data if isinstance(data, dict) else None


def clear_update_request() -> None:
    try:
        request_path().unlink()
    except OSError:
        pass


def validate_request(request: dict[str, Any]) -> Path:
    installer = Path(str(request.get("installer") or "")).expanduser()
    try:
        resolved = installer.resolve()
        root = updates_dir().resolve()
    except OSError as error:
        raise RuntimeError("Некорректный путь к установщику.") from error
    if root not in resolved.parents:
        raise RuntimeError("Установщик находится вне папки обновлений.")
    if not resolved.is_file():
        raise RuntimeError("Скачанный установщик не найден.")
    expected = str(request.get("sha256") or "").lower()
    if expected and sha256_file(resolved) != expected:
        raise RuntimeError("SHA-256 установщика не совпал.")
    return resolved


def installed_app_exe() -> Path:
    return Path(sys.executable).resolve()


def is_installed() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    exe_dir = installed_app_exe().parent
    local = os.environ.get("LOCALAPPDATA")
    if local:
        expected = (Path(local) / "Programs" / APP_NAME).resolve()
        if exe_dir == expected:
            return True
    if os.name != "nt":
        return False
    try:
        import winreg

        key_name = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_ID}_is1"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name) as key:
            location, _ = winreg.QueryValueEx(key, "InstallLocation")
        return exe_dir == Path(str(location)).resolve()
    except Exception:
        return False


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def build_update_script(installer: Path, app_exe: Path, pid: int) -> Path:
    script = updates_dir() / "apply_update.ps1"
    log_path = _data_root() / "logs" / "update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""$ErrorActionPreference = 'Stop'
$installer = {_ps_quote(str(installer))}
$appExe = {_ps_quote(str(app_exe))}
$logPath = {_ps_quote(str(log_path))}
$pidToWait = {int(pid)}
function Write-UpdateLog([string]$message) {{
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $logPath -Value "[$stamp] $message" -Encoding UTF8
}}
try {{
    Write-UpdateLog 'updater started'
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) -and ((Get-Date) -lt $deadline)) {{
        Start-Sleep -Milliseconds 500
    }}
    if (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{
        Write-UpdateLog 'main process did not exit, stopping it'
        Stop-Process -Id $pidToWait -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }}
    Write-UpdateLog 'running installer'
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS')
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    Write-UpdateLog "installer exit code: $($process.ExitCode)"
    if ($process.ExitCode -eq 0) {{
        Start-Sleep -Seconds 1
        Start-Process -FilePath $appExe
        Write-UpdateLog 'new version started'
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }} else {{
        Write-UpdateLog 'installer failed, keeping setup file'
    }}
}} catch {{
    Write-UpdateLog "update failed: $($_.Exception.Message)"
}} finally {{
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""
    script.write_text(content, encoding="utf-8-sig")
    return script


def launch_update(installer: Path, app_exe: Path, pid: int) -> Path:
    script = build_update_script(installer, app_exe, pid)
    creationflags = CREATE_NO_WINDOW
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ],
        cwd=str(updates_dir()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )
    return script
