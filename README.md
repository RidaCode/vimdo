# vimdo

A tiny Neovim practice game: pull real source code from GitHub, alter it, then restore the altered copy until it exactly matches the read-only original.

## What it looks like

`vimdo cpp` picks a real C++ file and launches:

```text
ORIGINAL (read-only)          CHALLENGE (you edit this)
────────────────────          ─────────────────────────
correct code                  altered code
correctName                   weirdName
42                            49
```

Neovim's built-in diff highlighting disappears as you repair the right side.

## Requirements

- Python 3.10+
- Git
- Neovim
- Internet access the first time a repository is cached

No GitHub token is required for the built-in public repositories.

## Install

```bash
./install.sh
```

Make sure `~/.local/bin` is in your `PATH`.

## Use

```bash
vimdo cpp
vimdo c
vimdo rust
vimdo python
vimdo javascript
vimdo go
```

Useful options:

```bash
vimdo cpp -m 15
vimdo cpp --repo fmtlib/fmt
vimdo cpp --min-lines 100 --max-lines 400
vimdo cpp --seed 1234
vimdo cpp --refresh
vimdo cpp --no-open
vimdo --resume
```

The built-in pool is only a starting point. `--repo owner/repo` lets you point it at any public GitHub repository containing the selected language.

## Rules / intended play

- Left pane is the real original and is locked read-only.
- Right pane is the altered challenge.
- Get the right pane byte-for-byte equal to the left pane.
- `]c` and `[c` jump between diff hunks.
- `do` / `dp` normal-mode diff-copy shortcuts are disabled so you actually practice editing.
- The mutation manifest is saved with the challenge, but hidden during normal play. Use `--show-mutations` only for debugging.

When Neovim exits, vimdo compares both files exactly. If you are not finished, it prints a resume command.

## Where things live

Repositories are cached under:

```text
~/.cache/vimdo/repos/
```

Challenges are preserved under:

```text
~/.local/state/vimdo/challenges/
```

That means you can quit midway and resume later with `vimdo --resume`.

## MVP mutation strategy

The first version deliberately stays dependency-free. It mutates:

- identifiers, often across every matching occurrence
- numeric literals
- string literals

It does not try to preserve compilation. The exercise is text manipulation, not understanding or fixing program semantics.

A future Tree-sitter version can distinguish function names, parameters, locals, members, strings, operators, comments, and language scopes more precisely.
