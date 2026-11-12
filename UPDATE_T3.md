# Update t3code on signal

## Use the node of t3.service

```bash
export $(systemctl show t3.service -p Environment --value | tr ' ' '\n' | grep '^PATH=')
```

## Install the newest t3

```bash
npm install -g t3@latest
```

## Check the installed version

```bash
npm ls -g t3
```

## Restart t3.service

```bash
sudo systemd-run --on-active=20 /bin/systemctl restart t3.service
```

## Check after the restart

```bash
systemctl status t3.service --no-pager
journalctl -u t3.service -n 50 --no-pager
```
