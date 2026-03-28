# git-review

A locally-hosted, air-gapped CLI tool that uses a large language model to automatically review git diffs and generate structured code review summaries — no external APIs, no internet connection required, no code ever leaves your machine.

Built with [Ollama](https://ollama.com) and [Qwen3-Coder](https://ollama.com/library/qwen3-coder), `git-review` segments diffs by file, reviews each independently, and synthesizes a cross-file summary with configurable review modes for general quality, security, and code style.

---

## Features

- **Fully local and air-gapped** — runs entirely on your machine via Ollama, no API keys or internet required
- **Per-file review** — diffs are segmented by file and reviewed independently to respect model context limits
- **Cross-file synthesis** — per-file reviews are synthesized into a consolidated overall summary
- **Configurable review modes** — tailor the review focus to what you actually need
- **Flexible output** — Markdown or plain text, printed to stdout or saved to a file
- **Any git repo** — works on any local git repository, any language

---

## Review Modes

## Review Modes

| Mode | Focus |
|---|---|
| `general` | Bugs, logic errors, and general code quality |
| `security` | Vulnerabilities, injection risks, hardcoded secrets, unsafe patterns |
| `style` | Naming conventions, readability, clean code principles |
| `migration` | Deprecated/removed Java APIs across version upgrades, compatibility issues, modern alternatives |
| `java` | Null safety, exception handling, resource leaks, misuse of collections |
| `concurrency` | Race conditions, deadlocks, missing synchronization, unsafe shared state |
| `performance` | Inefficient algorithms, unnecessary object creation, N+1 queries, memory inefficiencies |
| `dependency` | Outdated, vulnerable, or conflicting library versions |
| `test` | Test coverage gaps, weak assertions, missing edge cases, poor mock usage |
| `documentation` | Missing or outdated Javadoc/docstrings, unclear signatures, undocumented error conditions |
| `complexity` | Overly long methods, deep nesting, high cyclomatic complexity, refactoring opportunities |
| `api` | REST API naming, HTTP status codes, error response structure, input validation |
| `secrets` | Hardcoded passwords, API keys, tokens, connection strings, private keys |
| `sql` | Injection risks, inefficient queries, missing indexes, unhandled nulls, missing transactions |

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- `qwen3-coder:30b` model pulled via Ollama (or any other Ollama-hosted model)
- Git

---

## Installation

**1. Clone the repository:**
```bash
git clone https://github.com/schuyler-w/git-review.git
cd git-review
```

**2. Create and activate a virtual environment:**

With Conda (recommended):
```bash
conda create -n git-review python=3.11 -y
conda activate git-review
```

Or with venv:
```bash
python -m venv venv
source venv/Scripts/activate  # Windows (Git Bash)
source venv/bin/activate       # macOS/Linux
```

**3. Install dependencies:**
```bash
pip install openai gitpython click
```

**4. Pull the model via Ollama:**
```bash
ollama pull qwen3-coder:30b
```
> This is an ~19GB download. Requires at least 20GB VRAM to run fully on-GPU. The model runs entirely locally — no Ollama account or internet connection needed after download.

**5. (Windows/Conda only) Fix SSL environment variable:**
```bash
echo 'unset SSL_CERT_FILE' >> ~/.bashrc
source ~/.bashrc
```

---

## Usage

Run from inside any git repository:

```bash
python /path/to/git_review.py [OPTIONS]
```

Or if installed as a package (see [Install as CLI](#install-as-cli)):
```bash
git-review [OPTIONS]
```

### Options

```
--base    TEXT     Base commit or branch to diff from  [default: HEAD~1]
--head    TEXT     Head commit or branch to diff to    [default: HEAD]
--mode    TEXT     Review mode: general, security, style  [default: general]
--format  TEXT     Output format: markdown, plain  [default: markdown]
-o        FILE     Write output to a file instead of stdout
--help             Show this message and exit
```

### Examples

**Review your last commit:**
```bash
python git_review.py
```

**Review a feature branch against main:**
```bash
python git_review.py --base main --head my-feature-branch
```

**Security review of the last 3 commits:**
```bash
python git_review.py --base HEAD~3 --head HEAD --mode security
```

**Hunt for hardcoded secrets before pushing:**
```bash
python git_review.py --mode secrets
```

**Java version migration review, saved to file:**
```bash
python git_review.py --base old-version --head new-version --mode migration -o review.md
```

**Check for concurrency issues in a threading refactor:**
```bash
python git_review.py --base main --head concurrency-refactor --mode concurrency
```

**Performance review of a hot path change:**
```bash
python git_review.py --base HEAD~1 --head HEAD --mode performance
```

**Review test quality after adding a new feature:**
```bash
python git_review.py --mode test
```

**Check complexity before submitting a PR:**
```bash
python git_review.py --mode complexity
```

**Review Java-specific issues on a new module:**
```bash
python git_review.py --base main --head feature/new-module --mode java
```

**Audit dependency changes after a library upgrade:**
```bash
python git_review.py --base HEAD~1 --head HEAD --mode dependency
```

**Review REST API changes for design consistency:**
```bash
python git_review.py --base main --head feature/new-endpoints --mode api
```

**Check SQL query changes for injection risks and efficiency:**
```bash
python git_review.py --base HEAD~1 --head HEAD --mode sql
```

**Style review with plain text output for pasting into Jira:**
```bash
python git_review.py --mode style --format plain
```

**Documentation review of a new public API, saved to file:**
```bash
python git_review.py --base main --head feature/public-api --mode documentation -o docs-review.md
```

---

## Example Output

```
# Code Review

**Mode:** `security` | **Diff:** `HEAD~1..HEAD`

---

## `src/auth/login.py`

**Issues found:**

1. **SQL Injection (Critical)** — Line 14 constructs a raw SQL query using
   string formatting with unsanitized user input. Use parameterized queries instead.

2. **Hardcoded credential (High)** — `password = "admin123"` on line 4 is a
   hardcoded secret. Move to environment variables or a secrets manager.

3. **Shell injection risk (High)** — `subprocess.call(cmd, shell=True)` on line 21
   passes unsanitized input directly to the shell. Use a list of arguments and
   `shell=False` instead.

---

## Overall Summary

**Key Changes:** Modified authentication module with new user input handling and
query construction.

**Main Risks:** Three high-severity security issues identified — SQL injection,
hardcoded credentials, and shell injection. None should be merged without remediation.

**Recommended Follow-ups:**
- Replace raw SQL with parameterized queries throughout the auth module
- Audit the codebase for other hardcoded secrets
- Replace all `subprocess.call(..., shell=True)` usages
```

---

## Install as CLI

To run `git-review` as a command from anywhere without specifying the script path:

**1. Add a `setup.py` to the project root:**
```python
from setuptools import setup

setup(
    name="git-review",
    version="0.1.0",
    py_modules=["git_review"],
    install_requires=["openai", "gitpython", "click"],
    entry_points={"console_scripts": ["git-review=git_review:main"]},
)
```

**2. Install in editable mode:**
```bash
pip install -e .
```

**3. Run from any git repo:**
```bash
cd /path/to/any/repo
git-review --mode security
```

---

## Changing the Model

The model is set at the top of `git_review.py`:

```python
MODEL = "qwen3-coder:30b"
```

Swap it for any model you have pulled in Ollama. Recommended alternatives:

| Model | Size | Notes |
|---|---|---|
| `qwen3-coder:30b` | 19GB | Default — best balance of quality and speed |
| `qwen3-coder:30b-a3b-q8_0` | 32GB | Higher quality, needs 32GB+ VRAM |
| `codestral:22b` | ~13GB | Smaller, faster, good for style/general reviews |

---

## How It Works

1. Runs `git diff <base> <head>` via subprocess to get the raw unified diff
2. Splits the diff into per-file chunks by parsing `diff --git` headers
3. Sends each chunk to the locally-running LLM via Ollama's OpenAI-compatible API endpoint (`http://localhost:11434/v1`)
4. Collects per-file reviews and sends them together to the model for a consolidated synthesis
5. Formats the result as Markdown or plain text and prints to stdout or writes to file

Large file diffs are truncated at 12,000 characters to stay within the model's effective context for a single chunk.

---

## Privacy

All inference runs locally via Ollama. Your source code never leaves your machine and no internet connection is required after the initial model download. This makes `git-review` suitable for use on proprietary, classified, or otherwise sensitive codebases.

---

## License

MIT