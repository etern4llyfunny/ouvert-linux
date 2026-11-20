# Обновление ядра linux-ouvert

База: PKGBUILD `linux-cachyos-bore` (CachyOS).

1. Обновить хост и upstream-клон:
   ```zsh
   sudo pacman -Syu
   git -C ~/kernel/linux-cachyos-upstream pull
   ```
2. Подготовить сборочный каталог (4 правки PKGBUILD + шапка):
   ```zsh
   python ~/pzhavos/pkgbuilds/linux-ouvert/ouvert_kernel_prep.py \
     ~/kernel/linux-cachyos-upstream/linux-cachyos-bore \
     ~/kernel/linux-ouvert-<VER>
   ```
3. Собрать пакеты (`Enter` на возможных вопросах Kconfig `(NEW)`):
   ```zsh
   cd ~/kernel/linux-ouvert-<VER> && makepkg -sr
   rm -rf src pkg
   ```
4. Подписать пакеты ключом репозитория и проверить на хосте:
   ```zsh
   gpg --detach-sign --use-agent linux-ouvert-<VER>-x86_64.pkg.tar.zst
   gpg --detach-sign --use-agent linux-ouvert-headers-<VER>-x86_64.pkg.tar.zst
   sudo pacman -U linux-ouvert-<VER>-x86_64.pkg.tar.zst linux-ouvert-headers-<VER>-x86_64.pkg.tar.zst
   ```
   После ребута хоста проверить: `uname -r`, `dkms status`, `systemctl --failed`.
5. Обновить локальный каталог онлайн-репо и базу:
   ```zsh
   ln linux-ouvert*-<VER>-x86_64.pkg.tar.zst* ~/ouvert-online/x86_64/
   cd ~/ouvert-online/x86_64
   repo-add -v -R --sign ouvert.db.tar.gz linux-ouvert-<VER>-x86_64.pkg.tar.zst linux-ouvert-headers-<VER>-x86_64.pkg.tar.zst
   ```
6. Залить в релиз `x86_64` репозитория `etern4llyfunny/ouvert-repo` (не заливать `*.old`):
   ```zsh
   gh release upload x86_64 -R etern4llyfunny/ouvert-repo --clobber \
     linux-ouvert-<VER>-x86_64.pkg.tar.zst{,.sig} \
     linux-ouvert-headers-<VER>-x86_64.pkg.tar.zst{,.sig} \
     ouvert.db ouvert.db.sig ouvert.files ouvert.files.sig
   ```
   Удалить старые ассеты предыдущей версии ядра через `gh release delete-asset`.
7. Проверить обновление на установленной ВМ: `sudo pacman -Syu` -> ребут -> `uname -r && sysctl kernel.sched_bore && systemctl --failed`.
