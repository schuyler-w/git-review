import os
import click
import subprocess
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

MODEL = "qwen3-coder:30b"

REVIEW_PROMPTS = {
    "general": "You are a senior software engineer. Review this code diff and flag bugs, logic errors, and code quality issues. Be concise and specific.",
    "security": "You are a security engineer. Review this code diff for security vulnerabilities, injection risks, hardcoded secrets, and unsafe patterns. Be concise and specific.",
    "style": "You are a senior software engineer. Review this code diff for style issues, naming conventions, readability, and adherence to clean code principles. Be concise and specific.",
}

def get_diff(base: str, head: str) -> str:
    result = subprocess.run(
        ["git", "diff", base, head],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise click.ClickException(f"git diff failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        raise click.ClickException("No differences found between the specified refs.")
    return result.stdout

def split_by_file(diff: str) -> dict:
    chunks = {}
    current_file = None
    current_lines = []

    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git"):
            if current_file:
                chunks[current_file] = "".join(current_lines)
            parts = line.strip().split(" ")
            current_file = parts[-1][2:]  
            current_lines = [line]
        elif current_file:
            current_lines.append(line)

    if current_file and current_lines:
        chunks[current_file] = "".join(current_lines)

    return chunks

def review_chunk(filename: str, chunk: str, mode: str) -> str:
    if len(chunk) > 12000:
        chunk = chunk[:12000] + "\n... [truncated]"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REVIEW_PROMPTS[mode]},
            {"role": "user", "content": f"File: {filename}\n\n```diff\n{chunk}\n```"},
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content

def synthesize(file_summaries: dict, mode: str) -> str:
    combined = "\n\n".join(
        f"### {fname}\n{summary}" for fname, summary in file_summaries.items()
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a senior engineer. Given per-file code reviews, write a concise overall summary covering the key changes, main risks, and recommended follow-ups."},
            {"role": "user", "content": combined},
        ],
        max_tokens=512,
    )
    return response.choices[0].message.content

def format_output(file_summaries: dict, overall: str, mode: str, base: str, head: str, fmt: str) -> str:
    if fmt == "markdown":
        lines = [
            f"# Code Review\n",
            f"**Mode:** `{mode}` | **Diff:** `{base}..{head}`\n",
            "---\n",
        ]
        for fname, summary in file_summaries.items():
            lines.append(f"## `{fname}`\n{summary}\n")
        lines.append(f"---\n## Overall Summary\n{overall}")
        return "\n".join(lines)
    else:
        lines = [f"CODE REVIEW | mode={mode} | {base}..{head}", "=" * 60]
        for fname, summary in file_summaries.items():
            lines += [f"\n[{fname}]", summary]
        lines += ["\n" + "=" * 60, "OVERALL SUMMARY", overall]
        return "\n".join(lines)

@click.command()
@click.option("--base", default="HEAD~1", show_default=True, help="Base commit or branch to diff from.")
@click.option("--head", default="HEAD", show_default=True, help="Head commit or branch to diff to.")
@click.option("--mode", default="general", show_default=True,
              type=click.Choice(["general", "security", "style"]),
              help="Review mode.")
@click.option("--format", "fmt", default="markdown", show_default=True,
              type=click.Choice(["markdown", "plain"]),
              help="Output format.")
@click.option("--output", "-o", default=None, help="Write output to a file instead of stdout.")
def main(base, head, mode, fmt, output):
    """git-review: locally-hosted LLM-powered code review from git diffs."""
    click.echo(f"Diffing {base}..{head} in [{mode}] mode...", err=True)

    diff = get_diff(base, head)
    file_chunks = split_by_file(diff)
    click.echo(f"Reviewing {len(file_chunks)} file(s)...", err=True)

    file_summaries = {}
    for filename, chunk in file_chunks.items():
        click.echo(f"  → {filename}", err=True)
        file_summaries[filename] = review_chunk(filename, chunk, mode)

    click.echo("Synthesizing overall summary...", err=True)
    overall = synthesize(file_summaries, mode)

    result = format_output(file_summaries, overall, mode, base, head, fmt)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result)
        click.echo(f"Review written to {output}", err=True)
    else:
        click.echo(result)

if __name__ == "__main__":
    main()