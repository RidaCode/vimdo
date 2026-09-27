#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

APP = "vimdo"
VERSION = "0.1.1"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP / "repos"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP / "challenges"

LANGUAGES = {
    "cpp": {
        "label": "C++",
        "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h"],
        "repos": [
            "fmtlib/fmt",
            "gabime/spdlog",
            "catchorg/Catch2",
            "p-ranav/argparse",
            "CLIUtils/CLI11",
        ],
    },
    "c": {
        "label": "C",
        "extensions": [".c", ".h"],
        "repos": [
            "antirez/redis",
            "libuv/libuv",
            "curl/curl",
            "jqlang/jq",
            "DaveGamble/cJSON",
        ],
    },
    "rust": {
        "label": "Rust",
        "extensions": [".rs"],
        "repos": [
            "BurntSushi/ripgrep",
            "sharkdp/fd",
            "sharkdp/bat",
            "starship/starship",
            "nushell/nushell",
        ],
    },
    "python": {
        "label": "Python",
        "extensions": [".py"],
        "repos": [
            "psf/requests",
            "pallets/flask",
            "Textualize/rich",
            "tiangolo/fastapi",
            "httpie/cli",
        ],
    },
    "javascript": {
        "label": "JavaScript",
        "extensions": [".js", ".mjs", ".cjs"],
        "repos": [
            "axios/axios",
            "expressjs/express",
            "prettier/prettier",
            "lodash/lodash",
            "chalk/chalk",
        ],
    },
    "go": {
        "label": "Go",
        "extensions": [".go"],
        "repos": [
            "charmbracelet/bubbletea",
            "junegunn/fzf",
            "spf13/cobra",
            "gohugoio/hugo",
            "cli/cli",
        ],
    },
}

ALIASES = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "js": "javascript",
    "py": "python",
    "rs": "rust",
}

PROTECTED_IDENTIFIERS = {
    "std", "main", "self", "super", "this", "console", "printf", "malloc", "free",
    "true", "false", "null", "none", "nil",
}

COMMON_KEYWORDS = {
    # C/C++
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor", "bool",
    "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t", "class", "compl",
    "concept", "const", "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await",
    "co_return", "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else",
    "enum", "explicit", "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline",
    "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator",
    "or", "or_eq", "private", "protected", "public", "register", "reinterpret_cast", "requires", "return",
    "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct", "switch", "template",
    "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union", "unsigned",
    "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
    # Python
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in",
    "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    # JS
    "arguments", "await", "break", "case", "catch", "class", "const", "continue", "debugger", "default",
    "delete", "do", "else", "enum", "eval", "export", "extends", "false", "finally", "for", "function",
    "if", "implements", "import", "in", "instanceof", "interface", "let", "new", "null", "package", "private",
    "protected", "public", "return", "static", "super", "switch", "this", "throw", "true", "try", "typeof",
    "var", "void", "while", "with", "yield",
    # Go
    "break", "default", "func", "interface", "select", "case", "defer", "go", "map", "struct", "chan",
    "else", "goto", "package", "switch", "const", "fallthrough", "if", "range", "type", "continue", "for",
    "import", "return", "var",
    # Rust
    "as", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if",
    "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self", "Self",
    "static", "struct", "super", "trait", "true", "type", "unsafe", "use", "where", "while", "async", "await",
    "dyn",
}

NOISE_WORDS = [
    "ember", "quartz", "orbit", "pixel", "maple", "vector", "comet", "cinder",
    "signal", "harbor", "drift", "lumen", "echo", "frost", "raven", "delta",
]

EXCLUDE_PARTS = {
    ".git", ".github", "node_modules", "vendor", "third_party", "third-party", "external",
    "build", "dist", "target", "out", "generated", "docs", "examples/assets",
}

IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)(?![A-Za-z0-9_])")
STRING_RE = re.compile(r'(?P<q>["\'])(?P<body>(?:\\.|(?!\1).){2,80}?)(?P=q)')


@dataclass
class Mutation:
    kind: str
    before: str
    after: str
    occurrences: int


def die(message: str, code: int = 1) -> None:
    print(f"vimdo: {message}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    kwargs = {
        "cwd": str(cwd) if cwd else None,
        "check": check,
        "text": True,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    return subprocess.run(cmd, **kwargs)


def require_tools(no_open: bool) -> None:
    missing = [name for name in ["git"] if shutil.which(name) is None]
    if not no_open and shutil.which("nvim") is None:
        missing.append("nvim")
    if missing:
        die("missing required tool(s): " + ", ".join(missing))


def normalize_language(value: str) -> str:
    value = value.lower().strip()
    value = ALIASES.get(value, value)
    if value not in LANGUAGES:
        supported = ", ".join(LANGUAGES)
        die(f"unknown language '{value}'. Supported: {supported}")
    return value


def repo_cache_path(repo: str) -> Path:
    return CACHE_DIR / repo.replace("/", "__")


def ensure_repo(repo: str, refresh: bool) -> Path:
    cache = repo_cache_path(repo)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}.git"

    if not cache.exists():
        print(f"Fetching {repo} ...")
        try:
            run(["git", "clone", "--depth", "1", "--filter=blob:none", "--quiet", url, str(cache)])
        except subprocess.CalledProcessError:
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
            die(f"could not clone https://github.com/{repo}")
    elif refresh:
        print(f"Refreshing {repo} ...")
        try:
            run(["git", "fetch", "--depth", "1", "--quiet", "origin"], cwd=cache)
            branch = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=cache, capture=True, check=False)
            if branch.returncode == 0:
                remote_branch = branch.stdout.strip()
                run(["git", "reset", "--hard", "--quiet", remote_branch], cwd=cache)
        except subprocess.CalledProcessError:
            print("vimdo: refresh failed; using cached copy", file=sys.stderr)

    return cache


def is_excluded(path: Path) -> bool:
    normalized = "/".join(path.parts).lower()
    if any(part.lower() in EXCLUDE_PARTS for part in path.parts):
        return True
    return any("/" in pattern and pattern in normalized for pattern in EXCLUDE_PARTS)


def candidate_files(root: Path, extensions: list[str], min_lines: int, max_lines: int) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in extensions:
            continue
        rel = p.relative_to(root)
        if is_excluded(rel):
            continue
        try:
            if p.stat().st_size > 250_000:
                continue
            data = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = data.count("\n") + 1
        if min_lines <= lines <= max_lines:
            files.append(p)
    return files


def case_like(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source.islower():
        return replacement.lower()
    if source[:1].isupper() and source[1:].islower():
        return replacement.capitalize()
    if "_" in source:
        parts = re.split(r"_+", source)
        repl = [NOISE_WORDS[i % len(NOISE_WORDS)] for i in range(len(parts))]
        if source.isupper():
            return "_".join(x.upper() for x in repl)
        return "_".join(repl)
    # camelCase / PascalCase-ish
    chunks = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", source)
    if len(chunks) >= 2:
        words = [NOISE_WORDS[i % len(NOISE_WORDS)] for i in range(len(chunks))]
        first = words[0].capitalize() if source[:1].isupper() else words[0]
        return first + "".join(w.capitalize() for w in words[1:])
    return replacement


def fresh_identifier(old: str, used: set[str], rng: random.Random) -> str:
    for _ in range(100):
        raw = rng.choice(NOISE_WORDS)
        candidate = case_like(old, raw)
        if candidate != old and candidate not in used and candidate not in COMMON_KEYWORDS:
            return candidate
    return f"{old}_vimdo"


def identifier_candidates(text: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for token in IDENT_RE.findall(text):
        if token in COMMON_KEYWORDS or token.lower() in PROTECTED_IDENTIFIERS:
            continue
        if len(token) < 3 or token.startswith("__"):
            continue
        if token.isdigit():
            continue
        counts[token] = counts.get(token, 0) + 1
    # Prefer identifiers that repeat, but keep singles too.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def mutate_identifier(text: str, used: set[str], generated: set[str], rng: random.Random) -> tuple[str, Mutation] | None:
    candidates = [(name, count) for name, count in identifier_candidates(text) if name not in generated]
    if not candidates:
        return None
    # Bias toward repeated identifiers; they produce useful Vim practice.
    weighted = []
    for name, count in candidates:
        weight = min(count, 8)
        weighted.extend([(name, count)] * weight)
    old, count = rng.choice(weighted)
    new = fresh_identifier(old, used, rng)
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    # Do not rename text inside quoted strings. This is intentionally a small,
    # language-agnostic lexer rather than a semantic parser.
    protected = [(m.start(), m.end()) for m in STRING_RE.finditer(text)]
    pieces = []
    cursor = 0
    n = 0
    for match in pattern.finditer(text):
        if any(start <= match.start() < end for start, end in protected):
            continue
        pieces.append(text[cursor:match.start()])
        pieces.append(new)
        cursor = match.end()
        n += 1
    if n == 0:
        return None
    pieces.append(text[cursor:])
    mutated = "".join(pieces)
    used.add(new)
    generated.add(new)
    return mutated, Mutation("identifier", old, new, n)


def mutate_number(text: str, generated: set[str], rng: random.Random) -> tuple[str, Mutation] | None:
    matches = [m for m in NUMBER_RE.finditer(text) if m.group(0) not in generated]
    # Avoid changing a sea of 0/1 unless there are few other choices.
    interesting = [m for m in matches if m.group(0) not in {"0", "1"}] or matches
    if not interesting:
        return None
    m = rng.choice(interesting)
    old = m.group(0)
    if old.lower().startswith("0x"):
        value = int(old, 16)
        new = hex(value + rng.randint(1, 15))
    elif "." in old:
        try:
            value = float(old)
            new = str(round(value + rng.choice([0.5, 1.0, 2.0, 5.0]), 3)).rstrip("0").rstrip(".")
        except ValueError:
            return None
    else:
        value = int(old)
        delta = rng.choice([2, 3, 5, 7, 10, 16])
        new = str(value + delta)
    if new == old:
        return None
    mutated = text[:m.start()] + new + text[m.end():]
    generated.add(new)
    return mutated, Mutation("number", old, new, 1)


def mutate_string(text: str, generated: set[str], rng: random.Random) -> tuple[str, Mutation] | None:
    matches = []
    for m in STRING_RE.finditer(text):
        if m.group(0) in generated:
            continue
        body = m.group("body")
        if "\n" in body or body.isspace() or len(body.strip()) < 2:
            continue
        if m.group("q") == "'" and (len(body) == 1 or (body.startswith("\\") and len(body) <= 3)):
            continue
        # Avoid obvious includes/import paths and format-heavy strings in MVP.
        if body.endswith((".h", ".hpp", ".hh", ".py", ".js", ".go", ".rs")):
            continue
        matches.append(m)
    if not matches:
        return None
    m = rng.choice(matches)
    old_body = m.group("body")
    q = m.group("q")
    replacement_word = rng.choice(["VIMDO", "altered", "practice", "restore", "changed"])
    if " " in old_body:
        pieces = old_body.split()
        if pieces:
            pieces[rng.randrange(len(pieces))] = replacement_word
            new_body = " ".join(pieces)
        else:
            new_body = replacement_word
    else:
        new_body = replacement_word
    if new_body == old_body:
        new_body += "X"
    whole_old = m.group(0)
    whole_new = q + new_body + q
    mutated = text[:m.start()] + whole_new + text[m.end():]
    generated.add(whole_new)
    return mutated, Mutation("string", whole_old, whole_new, 1)


def create_mutations(original: str, requested: int, rng: random.Random) -> tuple[str, list[Mutation]]:
    text = original
    mutations: list[Mutation] = []
    used = set(IDENT_RE.findall(original))
    generated_identifiers: set[str] = set()
    generated_numbers: set[str] = set()
    generated_strings: set[str] = set()
    attempts = 0
    # Identifier-heavy because that's the most useful Vim exercise.
    kinds = ["identifier"] * 6 + ["number"] * 2 + ["string"] * 2

    while len(mutations) < requested and attempts < requested * 20:
        attempts += 1
        kind = rng.choice(kinds)
        result = None
        if kind == "identifier":
            result = mutate_identifier(text, used, generated_identifiers, rng)
        elif kind == "number":
            result = mutate_number(text, generated_numbers, rng)
        elif kind == "string":
            result = mutate_string(text, generated_strings, rng)
        if result is None:
            continue
        candidate_text, mutation = result
        # Avoid recording the exact same before token twice.
        if any(m.before == mutation.before and m.kind == mutation.kind for m in mutations):
            continue
        text = candidate_text
        mutations.append(mutation)

    return text, mutations


def challenge_dir(repo: str, relative_file: Path, seed: int) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha1(f"{repo}:{relative_file}:{seed}".encode()).hexdigest()[:7]
    return STATE_DIR / f"{stamp}-{digest}"


def write_metadata(path: Path, *, language: str, repo: str, relative_file: Path, seed: int, mutations: list[Mutation]) -> None:
    lines = [
        f"language={language}",
        f"repo={repo}",
        f"file={relative_file.as_posix()}",
        f"seed={seed}",
        f"mutations={len(mutations)}",
        "",
    ]
    for i, m in enumerate(mutations, 1):
        lines.append(f"{i:02d}. {m.kind}: {m.before!r} -> {m.after!r} ({m.occurrences} occurrence(s))")
    (path / "challenge.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_intro(language: str, repo: str, relative_file: Path, original: str, mutations: list[Mutation], path: Path) -> None:
    line_count = original.count("\n") + 1
    changed_occurrences = sum(m.occurrences for m in mutations)
    print()
    print("VIMDO")
    print("─────")
    print(f"Language : {LANGUAGES[language]['label']}")
    print(f"Source   : https://github.com/{repo}")
    print(f"File     : {relative_file.as_posix()} ({line_count} lines)")
    print(f"Mutations: {len(mutations)} edits / {changed_occurrences} changed occurrence(s)")
    print()
    print("Left  = altered challenge (edit this until the diff disappears)")
    print("Right = original reference (read-only)")
    print()
    print("Useful diff navigation: ]c next change, [c previous change")
    print("Diff-copy shortcuts do/dp are disabled so you practice editing.")
    print(f"Challenge files: {path}")
    print()


def launch_nvim(original: Path, challenge: Path) -> int:
    # Keep user's normal Neovim config. Lock the original and disable the convenient
    # diff-copy normal mappings in both panes so the exercise stays an editing drill.
    cmds = [
        "set diffopt+=vertical",
        "wincmd l",
        "setlocal readonly nomodifiable",
        "nnoremap <buffer> do <Cmd>echo 'vimdo: diff-copy disabled'<CR>",
        "nnoremap <buffer> dp <Cmd>echo 'vimdo: diff-copy disabled'<CR>",
        "wincmd h",
        "nnoremap <buffer> do <Cmd>echo 'vimdo: diff-copy disabled'<CR>",
        "nnoremap <buffer> dp <Cmd>echo 'vimdo: diff-copy disabled'<CR>",
    ]
    cmd = ["nvim", "-d", "-O", str(challenge), str(original)]
    for ex in cmds:
        cmd.extend(["-c", ex])
    return subprocess.call(cmd)


def remaining_diff(original: str, challenge: str) -> list[str]:
    return list(difflib.unified_diff(
        original.splitlines(), challenge.splitlines(),
        fromfile="original", tofile="challenge", lineterm=""
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vimdo",
        description="Restore altered real-world source code in Neovim diff mode.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("language", nargs="?", default="cpp", help="cpp, c, rust, python, javascript, go")
    parser.add_argument("--repo", help="GitHub repository as owner/repo (overrides the built-in pool)")
    parser.add_argument("-m", "--mutations", type=int, default=10, help="number of mutation actions (default: 10)")
    parser.add_argument("--min-lines", type=int, default=60, help="minimum source file length (default: 60)")
    parser.add_argument("--max-lines", type=int, default=260, help="maximum source file length (default: 260)")
    parser.add_argument("--seed", type=int, help="reproducible random seed")
    parser.add_argument("--refresh", action="store_true", help="refresh cached repository before picking a file")
    parser.add_argument("--no-open", action="store_true", help="create challenge but do not launch Neovim")
    parser.add_argument("--show-mutations", action="store_true", help="print mutation manifest (normally hidden)")
    parser.add_argument("--resume", action="store_true", help="resume the most recent unfinished challenge")
    return parser


def challenge_files(path: Path) -> tuple[Path, Path]:
    originals = sorted(path.glob("original.*"))
    challenges = sorted(path.glob("challenge.*"))
    challenges = [p for p in challenges if p.name != "challenge.txt"]
    if len(originals) != 1 or len(challenges) != 1:
        die(f"invalid challenge directory: {path}")
    return originals[0], challenges[0]


def report_result(original_path: Path, challenge_path: Path, elapsed: int) -> int:
    try:
        original = original_path.read_text(encoding="utf-8")
        final = challenge_path.read_text(encoding="utf-8")
    except OSError as exc:
        die(f"could not read challenge files: {exc}")

    if final == original:
        print()
        print("✓ RESTORED EXACTLY")
        print(f"  Time this session: {elapsed // 60:02d}:{elapsed % 60:02d}")
        return 0

    diff = remaining_diff(original, final)
    hunks = sum(1 for line in diff if line.startswith("@@"))
    changed_lines = sum(1 for line in diff if (line.startswith("+") or line.startswith("-")) and not line.startswith(("+++", "---")))
    print()
    print("Not restored yet.")
    print(f"Changed lines remaining: {changed_lines}")
    print(f"Diff hunks remaining   : {hunks}")
    print("Resume with: vimdo --resume")
    return 2


def resume_latest(no_open: bool) -> int:
    if not STATE_DIR.exists():
        die("no saved challenges yet")
    dirs = sorted((p for p in STATE_DIR.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dirs:
        die("no saved challenges yet")
    # Prefer the newest unfinished challenge.
    chosen = None
    for path in dirs:
        try:
            original_path, challenge_path = challenge_files(path)
            if original_path.read_bytes() != challenge_path.read_bytes():
                chosen = path
                break
        except OSError:
            continue
    if chosen is None:
        print("All saved challenges are already restored.")
        return 0
    original_path, challenge_path = challenge_files(chosen)
    print(f"Resuming: {chosen}")
    if no_open:
        print(f"Original : {original_path}")
        print(f"Challenge: {challenge_path}")
        return 0
    if shutil.which("nvim") is None:
        die("missing required tool: nvim")
    started = time.monotonic()
    launch_nvim(original_path, challenge_path)
    elapsed = int(time.monotonic() - started)
    return report_result(original_path, challenge_path, elapsed)


def main() -> int:
    args = build_parser().parse_args()
    if args.resume:
        return resume_latest(args.no_open)
    language = normalize_language(args.language)
    if args.mutations < 1 or args.mutations > 100:
        die("--mutations must be between 1 and 100")
    if args.min_lines < 1 or args.max_lines < args.min_lines:
        die("invalid line range")

    require_tools(args.no_open)
    seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(8), "big")
    rng = random.Random(seed)
    repo_candidates = [args.repo] if args.repo else list(LANGUAGES[language]["repos"])
    rng.shuffle(repo_candidates)
    repo = ""
    root = None
    files: list[Path] = []
    last_error = None
    for repo_candidate in repo_candidates:
        if not repo_candidate or "/" not in repo_candidate or repo_candidate.startswith("/") or repo_candidate.endswith("/"):
            die("--repo must look like owner/repo")
        try:
            candidate_root = ensure_repo(repo_candidate, args.refresh)
        except SystemExit as exc:
            if args.repo:
                raise
            last_error = exc
            continue
        candidate_list = candidate_files(candidate_root, LANGUAGES[language]["extensions"], args.min_lines, args.max_lines)
        if candidate_list:
            repo = repo_candidate
            root = candidate_root
            files = candidate_list
            break
        if args.repo:
            die(f"no suitable {LANGUAGES[language]['label']} files found in {repo_candidate} within {args.min_lines}-{args.max_lines} lines")

    if root is None or not files:
        die(f"could not find a suitable {LANGUAGES[language]['label']} source file in the built-in repository pool")

    rng.shuffle(files)
    chosen = None
    original = ""
    altered = ""
    mutations: list[Mutation] = []
    for file_path in files[:100]:
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        candidate, muts = create_mutations(text, args.mutations, rng)
        if len(muts) >= min(args.mutations, 3) and candidate != text:
            chosen = file_path
            original = text
            altered = candidate
            mutations = muts
            break
    if chosen is None:
        die("could not find a source file with enough safe mutation targets; try another repo or fewer mutations")

    relative_file = chosen.relative_to(root)
    out = challenge_dir(repo, relative_file, seed)
    out.mkdir(parents=True, exist_ok=False)
    suffix = chosen.suffix or ".txt"
    original_path = out / f"original{suffix}"
    challenge_path = out / f"challenge{suffix}"
    original_path.write_text(original, encoding="utf-8")
    challenge_path.write_text(altered, encoding="utf-8")
    write_metadata(out, language=language, repo=repo, relative_file=relative_file, seed=seed, mutations=mutations)

    print_intro(language, repo, relative_file, original, mutations, out)
    if args.show_mutations:
        print((out / "challenge.txt").read_text(encoding="utf-8"))

    if args.no_open:
        print(f"Open manually: nvim -d {challenge_path} {original_path}")
        return 0

    started = time.monotonic()
    launch_nvim(original_path, challenge_path)
    elapsed = int(time.monotonic() - started)
    result = report_result(original_path, challenge_path, elapsed)
    if result == 0:
        print(f"  Mutations repaired: {len(mutations)}")
        print(f"  Source: https://github.com/{repo}/blob/HEAD/{relative_file.as_posix()}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
