# Публикация Parsy на GitHub

Релиз `1.0.0` уже опубликован. Ниже — порядок выпуска `1.1.0` с AI-тренером и автообновлением.

## 1. Проверь сборку

```powershell
Set-Location "C:\Users\Admin\Desktop\parser_alpha_1_0"

.\.venv-build\Scripts\python.exe -m py_compile app.py advisor.py updater.py main.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Проверь вручную:

- AI-вкладка открывается и строит локальный план;
- установленная версия видит обновление;
- Portable показывает ссылку на GitHub вместо кнопки автообновления;
- после обновления сохраняются настройки и данные.

## 2. Сделай коммит и отправь код

```powershell
git status
git diff
git add app.py advisor.py updater.py main.py Parsy.spec build.ps1 version_info.txt installer\Parsy.iss README.md DESKTOP_BUILD.md PUBLISH.md docs\RELEASE_NOTES_1.1.0.md
git commit -m "Release Parsy 1.1.0"
git push
```

Не добавляй `dist`, `build`, `vendor` и `.venv-build` — они исключены через `.gitignore`.

## 3. Создай Release

В репозитории `https://github.com/dponeNF/parsy`: **Releases** → **Draft a new release**.

Заполни:

- **Choose a tag**: `v1.1.0`, создай новый тег от `main`;
- **Release title**: `Parsy 1.1.0`;
- **Describe this release**: вставь текст из `docs\RELEASE_NOTES_1.1.0.md`;
- **Attach binaries**:
  - `dist\Parsy-Setup-1.1.0.exe`
  - `dist\Parsy-Portable.zip`
  - `dist\SHA256SUMS.txt`

Не загружай папку `dist` целиком или `dist\Parsy` — только эти три файла.

Нажми **Publish release**. После публикации `releases/latest` должен указывать на `1.1.0`.

## 4. Проверь автообновление

1. Установи `Parsy-Setup-1.1.0.exe` поверх `1.0.0`.
2. Запусти Parsy и нажми «Проверить обновления».
3. Для проверки следующего релиза временно подними версию в тестовой сборке или используй локальный `PARSY_UPDATE_API`.
4. Убедись, что Setup скачивается, SHA-256 совпадает, приложение закрывается и запускается снова.
5. Проверь `%LOCALAPPDATA%\Parsy\logs\update.log`.

Updater выбирает первый ассет `Parsy-Setup-*.exe` в latest release. Если Setup не прикреплён или tag не содержит версию, обновление не сработает.

## 5. Важно

- GitHub принимает крупные файлы только как ассеты Release, не в обычный коммит.
- GitHub Release позволяет прикреплять файлы до 2 GB.
- Для публичной раздачи репозиторий должен быть **Public**.
- Установщик не подписан код-сертификатом: SmartScreen может показать предупреждение.
- Не коммить токены, пароли и личные ключи.
