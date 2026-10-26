# ForgePilot

**An evidence-first workflow skill for AI coding agents, with a read-only Python repository toolkit.**

ForgePilot helps coding agents investigate unfamiliar codebases, map architecture, plan minimal changes, debug systematically, and report verification honestly. It does not upgrade the underlying model or grant additional tools and permissions.

## Features

- Portable `SKILL.md` instructions for compatible coding agents
- Evidence / inference / unknown distinction
- Small-scope repository reconnaissance
- Minimal-patch and regression-check workflow
- Honest verification reporting
- Read-only Python CLI for Termux and other Python 3 environments
- No third-party Python dependencies

## Repository structure

```text
forgepilot/
├── SKILL.md
├── README.md
├── LICENSE
├── .gitignore
├── scripts/
│   └── forgepilot.py
├── references/
│   └── WORKFLOW.md
└── tests/
    └── test_forgepilot.py
```

## Run on Android with Termux

Install Termux from a trusted distribution source, open it, then run:

```bash
pkg update
pkg install python git
git clone https://github.com/YOUR-USERNAME/forgepilot.git
cd forgepilot
python scripts/forgepilot.py inspect .
python scripts/forgepilot.py check .
python scripts/forgepilot.py report .
```

Replace `YOUR-USERNAME` with your GitHub username after publishing. If you download the repository ZIP instead, extract it and `cd` into the extracted folder.

## Commands

### Inspect a repository

```bash
python scripts/forgepilot.py inspect /path/to/project
```

Prints a concise file inventory, common project markers, and counts of selected file types. Hidden folders and common generated/vendor folders are skipped by default.

### Run structural checks

```bash
python scripts/forgepilot.py check /path/to/project
```

Checks for common project markers and basic repository hygiene. This is not a compiler, security scanner, or correctness proof.

### Generate a text report

```bash
python scripts/forgepilot.py report /path/to/project
```

Prints an inspect-and-check report to the terminal. Redirect it to a file if desired:

```bash
python scripts/forgepilot.py report . > forgepilot-report.txt
```

## Install the skill into a compatible agent

Agent-specific skill directories vary. If your coding agent supports the open Agent Skills format, copy the whole `forgepilot` folder into that agent's configured skills directory and restart or refresh the agent if required. Consult that agent's official documentation for the correct location.

The portable core is `SKILL.md`; `scripts/` is optional. An agent that cannot load skills from a local folder may require a different integration method.

## Safety

- The bundled CLI is read-only.
- It does not run code from the target repository.
- It does not install dependencies or make network requests.
- Always inspect a skill before installing it into an agent that can edit files or run shell commands.
- The skill cannot override an agent platform's safety controls.

## Development and tests

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- [ ] Validate skill metadata in CI
- [ ] Add fixtures for more repository types
- [ ] Add optional JSON output for automated pipelines
- [ ] Document agent-specific installation paths with verified upstream links
- [ ] Add a release checklist and changelog

## License

MIT. See `LICENSE`.

### Validate the skill itself

```bash
python scripts/validate_skill.py
```

This checks basic frontmatter fields and local file references. It is not a full YAML parser or a guarantee of compatibility with every agent implementation.
