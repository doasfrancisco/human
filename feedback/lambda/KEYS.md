# User keys

One key per person. The key names the user, and the Lambda lets that key read and write only that user's sessions.

Make a key:

```bash
feedback/lambda/newkey.sh "Ana"
```

It writes `keys/<key>` in the bucket `human-training-<account>` with a random user id inside, and prints the line to send: `human login <key>`. The person runs that line once; it writes `~/.config/human/credentials.json` on their machine.

A session belongs to one user and one project. `human init` writes a project id into `human/human.json` — it goes into git with the map, so every machine and every teammate on the repo shares it — and every session carries that id. The CLI and the reader list the sessions of this key and this project only; a session from another project is out of sight, and never mixes in.

Take a key away:

```bash
aws s3 rm s3://human-training-<account>/keys/<key>
```

The sessions of that user stay in `sessions/<user id>/`.

Deploy or update the Lambda with `feedback/lambda/deploy.sh`. It prints the function URL; the CLI holds that URL in `compiler/cli/human/cmd_store.py`.
