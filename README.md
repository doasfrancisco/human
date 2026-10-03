# The human programming language

Human is the first open source AI programming language that makes it possible to code using LLMs.

## Setup

Requires [Claude Code](https://claude.com/claude-code).

```bash
curl -fsSL https://doashuman.com/install.sh | bash
```

On Windows, in PowerShell:

```powershell
irm https://doashuman.com/install.ps1 | iex
```

This installs human and the /human skill. A running `human serve` downloads each new version in the background and deploys the skills again; a click on the update button at the bottom right of the file tree restarts the server on it.

## Use

In your project:

```bash
human init            # creates the human/ folder: the maps live there
```

Then in Claude Code:

- `/human <abstraction>` — compile free text into code, mapped to your words.
- `/human how does <file> work?` — explain an existing file, pinned to its lines.

## Read

```bash
human serve
```

Open the link it prints, like `http://localhost:8010/<project id>/human/web.html`. One server reads every project of the machine: `human serve` in a second project gives it to the server that runs and prints its link. Every entry opens as a notepad, and "compile" hands your words to claude. A right click on the file tree gives "create file" and "create human"; "create file" makes an empty file, in a new folder too, under the folder you clicked; write its abstraction and claude writes the code under it.

Everything the project writes lives in the `human/` folder — one `rm -rf human/` removes it completely.
