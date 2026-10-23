# Parsy Desktop

Parsy — локальное Windows-приложение для разбора демок CS2. Внутри используется Streamlit, но пользователь запускает обычное нативное окно: браузер не открывается, сервер слушает только `127.0.0.1` на случайном порту и закрывается вместе с приложением.

## Готовые файлы

После сборки результаты лежат в `dist`:

- `Parsy-Setup-1.0.0.exe` — установщик для игроков.
- `Parsy-Portable.zip` — Portable-версия, которую нужно полностью распаковать.
- `Parsy\Parsy.exe` — распакованная Portable-папка.
- `SHA256SUMS.txt` — контрольные суммы артефактов.

Ориентировочные размеры текущей сборки:

- Portable-папка: 421 MB;
- ZIP: 149 MB;
- Setup: 102 MB.

## Для игрока

### Установщик

1. Запустить `Parsy-Setup-1.0.0.exe`.
2. Если Windows SmartScreen покажет предупреждение, нажать «Подробнее» → «Выполнить в любом случае». Установщик пока не подписан сертификатом.
3. Пройти установку. Права администратора не нужны: приложение ставится в `%LOCALAPPDATA%\Programs\Parsy`.
4. Запустить Parsy из меню «Пуск» или с рабочего стола.

Если Microsoft Edge WebView2 Runtime не установлен, установщик запустит официальный bootstrapper Microsoft. Для этого нужен интернет. WebView2 уже есть на большинстве Windows 10/11.

### Portable

1. Полностью распаковать `Parsy-Portable.zip` в обычную папку.
2. Запустить `Parsy.exe` из распакованной папки.
3. Не запускать `Parsy.exe` непосредственно из ZIP-архива.

На компьютере должен быть установлен WebView2 Runtime. Ссылка: `https://go.microsoft.com/fwlink/p/?LinkId=2124703`.

### Данные и логи

- Настройки WebView2: `%LOCALAPPDATA%\Parsy\webview2`
- Логи: `%LOCALAPPDATA%\Parsy\logs`
- `gui.log` — запуск окна, ошибки оболочки.
- `server.log` — запуск локального Streamlit-сервера.

Демка не отправляется на сервер. Наружу передаются только никнеймы и названия команд для карточек HLTV/Liquipedia, как указано в интерфейсе.

## Сборка

### Требования

- Windows 10/11 x64.
- Python 3.13 x64 с Launcher `py`.
- Inno Setup 6 или 7 — только если нужен Setup. Без него соберётся Portable.
- Интернет при первой сборке: pip-зависимости и bootstrapper WebView2.

### Одна команда

Из папки проекта:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Скрипт:

1. Создаёт `.venv-build`.
2. Ставит зависимости из `requirements-desktop.txt`.
3. Собирает `dist\Parsy\Parsy.exe` через `Parsy.spec`.
4. Создаёт `dist\Parsy-Portable.zip`.
5. Скачивает `vendor\MicrosoftEdgeWebView2Setup.exe`, если его нет.
6. Собирает `dist\Parsy-Setup-1.0.0.exe` через Inno Setup.

Полная сборка занимает примерно 6–10 минут.

Дополнительные режимы:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Clean
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -SkipInstaller
```

- `-Clean` удаляет `build` и `dist` перед сборкой.
- `-SkipInstaller` собирает только Portable.
- Если нужно пересоздать build-окружение, удалить `.venv-build` и запустить сборку снова.

### Если Inno Setup не установлен

`build.ps1` соберёт Portable и выведет предупреждение. Установить Inno Setup 6/7, затем выполнить:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ".\installer\Parsy.iss"
```

## Разработка

Установить desktop-зависимости:

```powershell
py -3 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-desktop.txt
```

Запуск нативного окна:

```powershell
.\.venv-build\Scripts\python.exe main.py
```

Обычный запуск Streamlit для отладки:

```powershell
py -m streamlit run app.py
```

## Как устроена оболочка

- `main.py` — точка входа desktop-приложения.
- При обычном запуске создаёт окно `pywebview`, splash и error-экран.
- Запускает дочерний процесс `Parsy.exe --streamlit-server ...` без консольного окна.
- Ждёт `http://127.0.0.1:<port>/_stcore/health`, затем загружает приложение в окно.
- При закрытии окна завершает дочерний процесс через `taskkill /PID ... /T /F`.
- Второй запуск не создаёт второе окно: приложение пытается вывести на передний план уже запущенный Parsy.
- `app.py` включён в сборку как файл данных, а не импортируется как модуль.

## Версия

При выпуске новой версии изменить:

1. `main.py` → `APP_VERSION`.
2. `version_info.txt` → `filevers`, `prodvers`, строковые версии.
3. `installer\Parsy.iss` → `#define MyAppVersion`.
4. `VersionInfoVersion` в `installer\Parsy.iss`.

После этого выполнить `build.ps1`. Имя Setup-файла изменится автоматически.

## Диагностика

### Окно не открывается

Проверить:

```text
%LOCALAPPDATA%\Parsy\logs\gui.log
```

Если в логе `E_ABORT` или ошибка WebView2, переустановить Microsoft Edge WebView2 Runtime.

### Приложение долго запускается

Первый запуск распакованной Portable-версии и первый разбор демки медленнее: Windows проверяет новые файлы, приложение загружает профили команд. Локальный сервер стартует несколько секунд.

### Антивирус

Неподписанный PyInstaller EXE может вызвать ложное срабатывание. Для публикации стоит подписать `Parsy.exe` и Setup код-сертификатом.

### Ошибка `Failed to download the Microsoft Edge WebView2 bootstrapper`

Проверить интернет и повторить сборку. Можно вручную скачать bootstrapper по ссылке Microsoft и положить его в:

```text
vendor\MicrosoftEdgeWebView2Setup.exe
```
