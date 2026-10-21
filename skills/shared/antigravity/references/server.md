# agy на Linux-сервере: изоляция, туннель, вход

Образец — сервер Netcup проекта smm-planner (`scripts/server_images.py`, `scripts/server_agy2.py`,
`docs/server-netcup.md`). Ниже — те же шаги с заменяемыми именами: `<agyuser>`, `<порт>` (SOCKS), `<выход>`.
Всё — от root, повторный запуск безопасен; ставить скриптом из проекта, а не руками.

## 1. Выход: один постоянный адрес на аккаунт

Сервер сам может быть не в той стране (или его адрес уже «чей-то»). Аккаунт ходит в Google с одного адреса через
SSH-туннель на сервер-выход (у нас — VPS в Нидерландах).

На сервере-выходе — пользователь только для туннеля:

```sh
useradd -r -m -d /home/<tunnel> -s /usr/sbin/nologin <tunnel>; passwd -l <tunnel>
install -d -m 700 -o <tunnel> -g <tunnel> /home/<tunnel>/.ssh
echo 'restrict,port-forwarding ssh-ed25519 AAAA… agy-tunnel@<сервер>' > /home/<tunnel>/.ssh/authorized_keys
chmod 600 /home/<tunnel>/.ssh/authorized_keys; chown <tunnel>: /home/<tunnel>/.ssh/authorized_keys
```

Второму аккаунту — **второй адрес** на том же выходе: свой туннельный пользователь, его соединения метятся
(`iptables -t mangle … --uid-owner … --ctdir ORIGINAL -j MARK`), своя таблица маршрутов с `unreachable` по
умолчанию (нет маршрута — нет утечки через адрес первого) и `SNAT --to-source <второй адрес>`; служба
`nl-exit2` в smm-planner `scripts/server_agy2.py` (`NL_EXIT2`).

На рабочем сервере — ключ и служба туннеля (ключ хоста выхода закрепить в `/root/.ssh/known_hosts`). Образец
ниже собран заново; живой рабочий — `nl-tunnel.service` на Netcup (`systemctl cat nl-tunnel`), сверить с ним:

```ini
# /etc/systemd/system/agy-tunnel.service
[Unit]
Description=SOCKS 127.0.0.1:<порт> через <выход> — только для agy
After=network-online.target
Wants=network-online.target

[Service]
Environment=AUTOSSH_GATETIME=0
ExecStart=/usr/bin/autossh -M 0 -N -D 127.0.0.1:<порт> -i /root/.ssh/agy_tunnel -p <ssh-порт выхода> \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes \
  <tunnel>@<выход>
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 2. Пользователь, установка, запрет прямой сети

```sh
useradd -m -s /bin/bash <agyuser>
install -d -o <agyuser> -g <agyuser> /home/<agyuser>/work      # доверенная рабочая папка
# установка — через туннель, чтобы и скачивание шло с того же адреса
sudo -u <agyuser> -H env HTTPS_PROXY=socks5h://127.0.0.1:<порт> bash -c \
  'curl -fsSL https://antigravity.google/cli/install.sh | bash'
```

ufw: всё исходящее от `<agyuser>`, кроме `lo` (то есть кроме туннеля), — `REJECT`. Строка — сразу после
`-A ufw-before-output -o lo -j ACCEPT` в `/etc/ufw/before.rules` и `ufw6-before-output` в `before6.rules`:

```sh
U=$(id -u <agyuser>)
for pair in /etc/ufw/before.rules:ufw-before-output /etc/ufw/before6.rules:ufw6-before-output; do
  f=${pair%%:*}; c=${pair##*:}
  grep -q '<agyuser>-only-tunnel' $f && continue
  cp -a $f $f.bak-$(date +%F)
  grep -q "^-A $c -o lo -j ACCEPT" $f
  sed -i "/^-A $c -o lo -j ACCEPT/a # <agyuser>-only-tunnel\n-A $c -m owner --uid-owner $U -j REJECT" $f
done
ufw reload
```

## 3. Обёртка запуска

```sh
#!/bin/sh
# /usr/local/bin/agy-<имя>: agy от <agyuser> только через туннель
P=socks5h://127.0.0.1:<порт>
cd /home/<agyuser>/work || exit 1
exec sudo -u <agyuser> -H env HTTPS_PROXY=$P HTTP_PROXY=$P ALL_PROXY=$P NO_PROXY= /home/<agyuser>/.local/bin/agy "$@"
```

`socks5h` — имена тоже разрешаются на выходе (DNS не утекает с сервера).

## 4. Второй аккаунт на том же сервере

Отдельно всё, по чему Google может связать аккаунты: свой пользователь, своя копия бинарника (папку `~/.gemini`
не копировать — `installation_id` должен быть свой), свой туннель и выход, свои `machine-id` и имя хоста:

```sh
install -d -m 755 /var/lib/<agyuser2>
od -An -N16 -tx1 /dev/urandom | tr -d ' \n' > /var/lib/<agyuser2>/machine-id; echo >> /var/lib/<agyuser2>/machine-id
echo "srv-$(od -An -N3 -tx1 /dev/urandom | tr -d ' \n')" > /var/lib/<agyuser2>/hostname
```

```sh
#!/bin/sh
# /usr/local/bin/agy-<имя2>: свои machine-id и имя хоста (пространства имён mount и uts), свой туннель
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"
exec unshare -m -u --propagation private sh -c '
mount --bind /var/lib/<agyuser2>/machine-id /etc/machine-id
[ -f /var/lib/dbus/machine-id ] && mount --bind /var/lib/<agyuser2>/machine-id /var/lib/dbus/machine-id
hostname "$(cat /var/lib/<agyuser2>/hostname)"
cd /home/<agyuser2>/work || exit 1
P=socks5h://127.0.0.1:<порт2>
exec setpriv --reuid=<agyuser2> --regid=<agyuser2> --init-groups --reset-env \
  env HTTPS_PROXY=$P HTTP_PROXY=$P ALL_PROXY=$P NO_PROXY= /home/<agyuser2>/.local/bin/agy "$@"' agy2 "$@"
```

Вход второго — в отдельном профиле браузера, который ходит через тот же второй выход: Chrome
`--user-data-dir=<свой профиль> --proxy-server=socks5://127.0.0.1:<локальный порт>` и
`--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"`, `--force-webrtc-ip-handling-policy=disable_non_proxied_udp`,
порт — `ssh -N -L <локальный порт>:127.0.0.1:<порт2> <сервер>` (smm-planner `server_agy2.py --browser`).

## 5. Вход по ссылке и коду

```sh
tmux new-session -d -s agy-login -x 220 -y 50 /usr/local/bin/agy-<имя>; sleep 10
tmux capture-pane -p -J -t agy-login -S -80        # экран: меню входа или ссылка
tmux send-keys -t agy-login Enter                   # выбрать «Google» в меню
```

1. Ссылку `https://accounts.google.com/…` склеить из строк экрана, открыть на ПК **через выход аккаунта** (VPN
   на тот же адрес или профиль из п. 4).
2. Войти, принять условия (решает человек), скопировать код со страницы `antigravity.google`.
3. Код — **не вставкой в `tmux attach` по SSH** (портится: «Malformed auth code»), а так: человек вводит его на ПК в
   скрытую строку, скрипт отправляет `tmux send-keys -t agy-login -l -- '<код>'`, затем `Enter`.
4. В окне — `/usage`: строки квоты есть, нет «(Antigravity Starter Quota)». Окно закрыть: `tmux kill-session`.

Файл входа — `/home/<agyuser>/.gemini/antigravity-cli/antigravity-oauth-token` (600). Перенос входа на другую
машину = вход с нового адреса; так не делать (правило «один адрес»).

## 6. Помощник для служб

Службы проекта работают от своего пользователя и agy напрямую не зовут:

- помощник `/usr/local/sbin/<проект>-agy` от root (внутри — `scripts/agy.py` с `AGY_CMD=/usr/local/bin/agy-<имя>`,
  `AGY_HOME=/home/<agyuser>`, `AGY_STATE=/var/lib/<проект>-agy`, `AGY_LOCK=/run/<аккаунт>.lock`);
- `/etc/sudoers.d/<проект>-agy`: `<служба> ALL=(root) NOPASSWD: /usr/local/sbin/<проект>-agy`, права 440,
  `visudo -cf`;
- промпт, схема, образец — через stdin или копией в `/home/<agyuser>/work`: `<agyuser>` файлов проекта не видит;
- папка состояния — `install -d -o root -g <группа> -m 2775`, журнал `journal.jsonl` 664;
- долгие задачи (код по ТЗ) — `systemd-run --unit agy-dev-<имя> -p MemoryMax=900M -p RuntimeMaxSec=4h …`.

## 7. Проверка

```sh
systemctl is-active agy-tunnel
curl -s --max-time 10 -x socks5h://127.0.0.1:<порт> https://ipinfo.io/ip      # = <выход>
sudo -u <agyuser> curl -s --max-time 5 https://ipinfo.io/ip && echo 'ОТКРЫТО — ошибка' || echo 'закрыто'
/usr/local/bin/agy-<имя> -p /usage --print-timeout 45s                         # строки Limit Remaining
cut -c1-8 /home/<agyuser>/.gemini/antigravity-cli/installation_id            # у второго — другой
```

## 8. Откат

`systemctl disable --now agy-tunnel`; `userdel -r <agyuser>`; `rm /usr/local/bin/agy-<имя>
/etc/systemd/system/agy-tunnel.service /etc/sudoers.d/<проект>-agy`; строки `<agyuser>-only-tunnel` из
`/etc/ufw/before*.rules` и `ufw reload`. На выходе: `userdel -r <tunnel>`.
