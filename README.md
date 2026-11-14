# Ouvert Linux

Дистрибутив на базе Arch Linux с собственным графическим установщиком.

Статус: бета. До версии 1.0 действует фриз фич, список блокеров релиза — в [RELEASE_BLOCKERS.md](RELEASE_BLOCKERS.md).

## Что внутри

- `installer/` — установщик на Python и PySide6, работает поверх archinstall
- `iso/` — профиль archiso и `build.sh` для сборки live-образа
- `pkgbuilds/` — исходники собственных пакетов (брендинг, keyring)
- `repo/` — база локального репозитория, из которого собирается ISO (сами пакеты в git не хранятся)

Установленная система получает обновления своих пакетов из подписанного репозитория [ouvert-repo](https://github.com/etern4llyfunny/ouvert-repo). Ядро `linux-ouvert` — собственный пакет ядра, собранный на основе PKGBUILD CachyOS.

## Сборка

Нужен Arch Linux с пакетом `archiso`:

    cd iso && sudo ./build.sh

Сборка пока рассчитана на машину автора: путь к локальному репозиторию жёстко прописан в `iso/profile/pacman.conf`, а пакеты для него нужно собрать самостоятельно.

## Лицензия

GPL-3.0-or-later, текст — в [LICENSE](LICENSE).
