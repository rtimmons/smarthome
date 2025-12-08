# Reference repos

Upstream Home Assistant repos tracked here as read-only submodules for quick reference.

## Working with them
- Re-init after a fresh clone or if you `rm -rf reference-repos/*`: `git submodule update --init --recursive reference-repos`
- Refresh to the latest default branch (branches pinned in `.gitmodules`): `git submodule update --remote reference-repos/<name>`
- Keep changes out of tree; these are for reading and cross-referencing only.

## Repo quick facts
- `reference-repos/developers.home-assistant` — Source for the developer docs site (developers.home-assistant.io). Docs entry: `README.md` for local tooling; content lives under `docs/` and `blog/` (Docusaurus). Add-on development entry point: `docs/add-ons.md` (tutorial, config, comms, testing, publishing).
- `reference-repos/home-assistant.io` — Source for the public website and user docs (Jekyll). Docs entry: `README.md`; documentation lives under `source/` (notably `_docs/` and `_integrations/`).
- `reference-repos/operating-system` — Home Assistant Operating System Buildroot tree and tooling. Docs entry: `Documentation/README.md` (plus the top-level `README.md` overview).
- `reference-repos/supervisor` — Home Assistant Supervisor runtime and host management. Docs entry: `README.md`, repo `AGENTS.md`, and developer guide at https://developers.home-assistant.io/docs/supervisor/development.
- `reference-repos/addons` — Official add-ons repo; see `README.md` plus individual add-on `README.md` files for base image usage and metadata conventions.
- `reference-repos/frontend` — Home Assistant frontend source; start at `README.md` for build/dev commands and links to the upstream frontend developer guide.
- `reference-repos/just` — Upstream `just` command runner. Docs entry: `README.md` (comprehensive 4,700+ line manual that mirrors the [Just manual](https://just.systems/man/en/)). The book content is generated from the README using `crates/generate-book/` and outputs to `book/en/` (English) and `book/zh/` (Chinese) directories. For complete documentation on recipe syntax, variables, functions, settings, and built-in behaviors when adjusting or troubleshooting `just` workflows, read the full `README.md` file directly.

## Accessing the Just Book

The `just` documentation is available in multiple formats:

### Primary Source
- **`reference-repos/just/README.md`** — The complete manual (4,700+ lines) containing all documentation
- **`reference-repos/just/README.中文.md`** — Chinese version of the manual

### Generated Book Structure
The mdBook format is generated from the README files but the source files may not be present in the submodule:
- **`reference-repos/just/book/en/`** — English book configuration (`book.toml`)
- **`reference-repos/just/book/zh/`** — Chinese book configuration (`book.toml`)
- **`reference-repos/just/crates/generate-book/`** — Rust crate that generates book chapters from README

### Online Resources
- **[just.systems/man/en/](https://just.systems/man/en/)** — Official online book (reflects latest release)
- **[GitHub README](https://github.com/casey/just/blob/master/README.md)** — Latest master branch version

### Key Documentation Sections
The README covers all essential topics including:
- Installation and setup
- Basic recipe syntax and parameters
- Variables, functions, and expressions
- Dependencies and conditional execution
- Shell configuration and environment variables
- Command line completion and advanced features
