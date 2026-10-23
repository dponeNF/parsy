# Публикация Parsy на GitHub

Локальный репозиторий уже подготовлен: файлы добавлены в индекс Git, `.gitignore` исключает сборки, демки и виртуальное окружение. Коммит не сделан специально, чтобы он был подписан твоим именем и email. Осталось создать репозиторий на GitHub, сделать коммит, отправить его и оформить Release.

## 1. Создай пустой репозиторий

На GitHub: **New repository**.

- Имя: `parsy` или другое;
- Видимость: **Public**, если приложение должно быть доступно всем;
- **Не добавляй** README, `.gitignore` и лицензию — они уже есть локально.

После создания скопируй URL вида:

```text
https://github.com/ТВОЙ_НИК/parsy.git
```

## 2. Сделай коммит

В PowerShell:

```powershell
Set-Location "C:\Users\Admin\Desktop\parser_alpha_1_0"

git config user.name "Твоё Имя"
git config user.email "твой@email"

git commit -m "Initial Parsy release v1.0.0"
```

Email лучше указывать тот же, что привязан к GitHub. Если не хочешь публиковать личный email, включи в GitHub приватный email и используй адрес вида `12345678+ТВОЙ_НИК@users.noreply.github.com`.

## 3. Отправь код на GitHub

```powershell
git remote add origin https://github.com/ТВОЙ_НИК/parsy.git
git push -u origin main
```

Если Git попросит авторизацию, откроется браузер Git Credential Manager. Обычный пароль GitHub не подойдёт: нужен вход через браузер или Personal Access Token.

Если `origin` уже существует:

```powershell
git remote set-url origin https://github.com/ТВОЙ_НИК/parsy.git
git push -u origin main
```

## 4. Создай Release

В репозитории: **Releases** → **Draft a new release**.

Заполни:

- **Choose a tag**: `v1.0.0`, создай новый тег от `main`;
- **Release title**: `Parsy 1.0.0`;
- **Describe this release**: вставь текст из `docs\RELEASE_NOTES_1.0.0.md`;
- **Attach binaries**: прикрепи три файла:
  - `dist\Parsy-Setup-1.0.0.exe`
  - `dist\Parsy-Portable.zip`
  - `dist\SHA256SUMS.txt`

Не загружай папку `dist` целиком или `dist\Parsy` — только эти три файла. Нажми **Publish release**.

После публикации ссылка для скачивания будет такой:

```text
https://github.com/ТВОЙ_НИК/parsy/releases/latest
```

## 5. Проверь результат

- Открой README на GitHub: описание, скриншот и ссылки должны отображаться.
- Открой Release и скачай Setup.
- Установи и запусти Parsy.
- Проверь, что в Release прикреплены все три файла.
- Ссылку на `releases/latest` можно давать игрокам.

## 6. Настрой репозиторий по желанию

В **About** справа на странице репозитория:

- Description: `Локальный разбор демок CS2 в нативном Windows-приложении`;
- Topics: `cs2`, `counter-strike-2`, `demo-parser`, `streamlit`, `pywebview`, `windows`;
- Social preview: загрузи `docs\parsy-preview.png`.

Если проект публичный и ты хочешь разрешить использование и модификацию кода, добавь файл `LICENSE` (например, MIT). Сейчас лицензия не задана.

## Важно

- Не добавляй в Git папки `dist`, `build`, `vendor` и `.venv-build` — они исключены через `.gitignore`.
- Установщик и Portable-архив больше 100 MB, поэтому GitHub не примет их в обычный коммит. Они загружаются только как файлы Release.
- GitHub Release позволяет прикреплять файлы до 2 GB.
- Если репозиторий приватный, скачать релиз смогут только приглашённые пользователи. Для публичной раздачи нужен **Public**-репозиторий.
- Не коммить токены, пароли и личные ключи.
