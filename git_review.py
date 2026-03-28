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
    "migration": "You are a senior Java engineer. Review this code diff in the context of a JDK 1.8 to JDK 21 migration. Flag deprecated or removed API usage, compatibility issues, and suggest modern JDK 21 alternatives where applicable. Be concise and specific.",
    "java": "You are a senior Java engineer. Review this code diff for Java-specific issues including null safety, improper exception handling, resource leaks, misuse of collections, and violations of Java best practices. Be concise and specific.",
    "concurrency": "You are a senior engineer specializing in concurrent systems. Review this code diff for concurrency issues including race conditions, deadlocks, missing synchronization, unsafe shared state, and improper use of threading primitives. Be concise and specific.",
    "performance": "You are a senior performance engineer. Review this code diff for performance issues including inefficient algorithms, unnecessary object creation, N+1 query patterns, missing caching opportunities, and memory inefficiencies. Be concise and specific.",
    "dependency": "You are a senior software engineer specializing in dependency management. Review this code diff for dependency issues including outdated library versions, known vulnerable dependencies, version conflicts, and unnecessary or redundant dependencies. Be concise and specific.",
    "test": "You are a senior software engineer specializing in software quality. Review this code diff for test quality issues including missing edge case coverage, weak or trivial assertions, improper use of mocks, missing error path tests, and tests that don't actually validate behavior. Be concise and specific.",
    "documentation": "You are a senior software engineer. Review this code diff for documentation issues including missing or outdated Javadoc and docstrings, unclear method signatures, missing parameter and return documentation, and undocumented error conditions. Be concise and specific.",
    "complexity": "You are a senior software engineer. Review this code diff for complexity issues including overly long methods, deep nesting, high cyclomatic complexity, violation of the single responsibility principle, and opportunities to refactor into cleaner abstractions. Be concise and specific.",
    "api": "You are a senior API design engineer. Review this code diff for REST API design issues including inconsistent naming conventions, incorrect HTTP status codes, poor error response structure, missing input validation, and versioning concerns. Be concise and specific.",
    "secrets": "You are a security engineer specializing in secrets management. Review this code diff exclusively for hardcoded secrets including passwords, API keys, tokens, connection strings, private keys, and any other sensitive values that should not be committed to source control. Be concise and specific.",
    "sql": "You are a senior database engineer. Review this code diff for SQL issues including injection vulnerabilities, inefficient queries, missing indexes, improper use of joins, unhandled null values in queries, and missing transaction boundaries. Be concise and specific.",
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
              type=click.Choice([
                  "general", "security", "style", "migration",
                  "java", "concurrency", "performance", "dependency",
                  "test", "documentation", "complexity", "api",
                  "secrets", "sql"
              ]),
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