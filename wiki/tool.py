"""Allowlisted static documentation and deployment transactions. Never queries HA state."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
from urllib.parse import quote, unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "wiki"
BUILD = ROOT / "build/wiki"
CATALOG = PROJECT / "components.json"
REVIEWS = PROJECT / "reviews.json"
REPO_URL = "https://github.com/rtimmons/smarthome/blob/"


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def safe_file(relative: str, root=ROOT):
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Not a regular confined source file: {relative}")
    return path


def source_files(component, root=ROOT):
    # Git's tracked-file list prevents ignored secrets and local runtime artifacts
    # from becoming review inputs. Explicit new source paths can be reviewed pre-commit.
    known = set(subprocess.check_output(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"], text=True).splitlines())
    import fnmatch
    matched = set()
    for pattern in component["watch"]:
        matches = {p for p in known if fnmatch.fnmatchcase(p, pattern) and (root / p).is_file()}
        if not any(c in pattern for c in "*?[") and (root / pattern).is_file():
            matches.add(pattern)
        matched.update(matches)
    return sorted(matched)


def fingerprint(paths, root=ROOT):
    return digest(json.dumps({p: digest(safe_file(p, root).read_bytes()) for p in sorted(set(paths))},
                             sort_keys=True).encode())


def catalog():
    return json.loads(CATALOG.read_text())


def check_reviews():
    data = catalog()
    reviews = json.loads(REVIEWS.read_text())
    errors = []
    for component in data["components"]:
        key = component["id"]
        record = reviews.get(key, {})
        expected = fingerprint(source_files(component))
        if record.get("fingerprint") != expected or not record.get("reason") or not record.get("reviewed_at"):
            errors.append(f"{key}: review its guide, then run just wiki-review {key} 'explanation of review'")
        for page in component["pages"]:
            safe_file(page)
    manifests = {p.parent.name for p in ROOT.glob("*/addon.yaml")}
    covered = {name for c in data["components"] for name in c.get("addons", [])}
    if manifests != covered:
        errors.append(f"Add-on coverage differs: {sorted(manifests ^ covered)}")
    if errors:
        raise ValueError("Documentation review required:\n" + "\n".join(errors))


def review(component_id, reason):
    if len(reason.strip()) < 15:
        raise ValueError("Give a meaningful review or no-impact explanation (at least 15 characters).")
    components = {c["id"]: c for c in catalog()["components"]}
    if component_id not in components:
        raise ValueError(f"Unknown component: {component_id}")
    reviews = json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {}
    reviews[component_id] = {"fingerprint": fingerprint(source_files(components[component_id])),
                             "reviewed_at": datetime.now(timezone.utc).date().isoformat(), "reason": reason}
    write_json(REVIEWS, reviews)


def source_url(path, revision):
    return REPO_URL + revision + "/" + quote(path, safe="/")


def table(headers, rows):
    def cell(x):
        return escape(str(x)).replace("|", "&#124;").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                      *["| " + " | ".join(cell(x) for x in row) + " |" for row in rows]]) + "\n"


def export_reference(stage):
    # Execute the model in its existing pinned Node/TypeScript environment.
    run(["just", "wiki-model-export"], cwd=ROOT)
    model = json.loads((BUILD / "model.json").read_text())
    services = []
    for path in sorted(ROOT.glob("*/addon.yaml")):
        addon = yaml.safe_load(path.read_text())
        services.append([addon["name"], path.parent.name,
                         "disabled / retained" if addon.get("disabled") else "enabled",
                         ", ".join(str(p) for p in addon.get("ports", {})),
                         ", ".join(addon.get("depends_on", [])) or "—"])
    target = stage / "reference"
    target.mkdir(parents=True)
    (target / "index.md").write_text("# Repository configuration\n\n"
        "These tables are generated from repository sources. They do not establish live availability, "
        "device inclusion, or a successful deployment.\n\n## Services\n\n" +
        table(["Service", "Source", "Desired status", "Ports", "Dependencies"], services) +
        "\n## Devices\n\n" + table(["Logical name", "Entity", "Type", "Inventory", "Scenes", "Include in all-off", "Allow scene off"],
        [[d["key"], d["entity"], d["type"], d["inventoryStatus"], d["sceneStatus"], d["includeInAllOff"], d["allowSceneTurnOff"]]
         for d in model["devices"]]) + "\n## Scenes and rooms\n\n"
        "Room labels below come from scene names; targets are declared membership, before the generator "
        "applies exclusions and health filtering. Use fast-scene scripts for operation.\n\n" +
        table(["Scene / room", "Operational script", "Declared targets"],
              [[s["name"], s["script"], ", ".join(s["targets"])] for s in model["scenes"]]))


def publication_inputs():
    data = catalog()
    paths = ["wiki/components.json", "wiki/reviews.json", "wiki/tool.py", "wiki/pyproject.toml", "wiki/uv.lock",
             "wiki/apply.sh", "wiki/transfer.py", "wiki/run"]
    paths += [p for c in data["components"] for p in c["pages"] + source_files(c)]
    paths += list(data["imports"])
    paths += [str(p.relative_to(ROOT)) for folder in (PROJECT / "assets", PROJECT / "theme", ROOT / "usenet-infra/wiki")
              for p in folder.rglob("*") if p.is_file()]
    return fingerprint(paths)


def rewrite_links(text, source, destination, mapping, revision):
    def replace(match):
        prefix, reference, suffix = match.groups()
        if reference == "wiki-reference:inventory":
            return prefix + os.path.relpath("reference/index.md", Path(destination).parent) + suffix
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        resolved = (ROOT / source).parent.joinpath(unquote(parsed.path)).resolve()
        if not resolved.is_relative_to(ROOT):
            raise ValueError(f"Link escapes repository: {source}: {reference}")
        relative = str(resolved.relative_to(ROOT))
        if relative in mapping:
            result = os.path.relpath(mapping[relative], Path(destination).parent)
            if parsed.fragment:
                result += "#" + parsed.fragment
        else:
            # Non-imported runbooks/source links remain explicit source references.
            # Never turn private or ignored files into a web link.
            if subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", relative],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                raise ValueError(f"Unpublished local link in {source}: {reference}")
            result = source_url(relative, revision)
            if parsed.fragment:
                result += "#" + parsed.fragment
        return prefix + result + suffix
    return re.sub(r"(\]\()([^\s)]+)(\))", replace, text)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.assets = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("script", "img", "iframe") and a.get("src"):
            self.assets.append(a["src"])
        if tag == "link" and a.get("rel") in ("stylesheet", "icon"):
            self.assets.append(a.get("href", ""))
        if tag in ("iframe", "object", "embed"):
            self.errors.append(f"Forbidden embedded content: {tag}")
        if tag == "script" and not a.get("src"):
            self.errors.append("Inline scripts are not publishable")
        if any(key.startswith("on") for key in a):
            self.errors.append("Inline event handlers are not publishable")


def validate_site(site):
    pages = {}
    for path in site.rglob("*.html"):
        parser = PageParser()
        parser.feed(path.read_text())
        pages[path.resolve()] = parser
    errors = []
    for path, parser in pages.items():
        errors.extend(parser.errors)
        for value in parser.assets:
            if urlsplit(value).scheme or value.startswith("//"):
                errors.append(f"Remote runtime asset: {value}")
        for value in parser.links + parser.assets:
            url = urlsplit(value)
            if url.scheme in ("javascript", "data", "vbscript"):
                errors.append("Executable or embedded URL rejected")
            if re.search(r"(?:api[_-]?key|token|password|auth)=", url.query, re.I):
                errors.append("Credential-bearing link rejected")
            if url.scheme or url.netloc or value in ("#", ""):
                continue
            target = ((site / url.path.lstrip("/")) if url.path.startswith("/") else path.parent / unquote(url.path)).resolve()
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(site.resolve()) or not target.is_file():
                errors.append(f"Broken local link: {path.relative_to(site)} → {value}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                # Theme dialog links are populated by the theme; source anchors are checked normally.
                errors.append(f"Broken fragment: {path.relative_to(site)} → {value}")
    for path in site.rglob("*"):
        if path.is_symlink():
            errors.append("Symlinks are not publishable")
        if path.is_file() and path.suffix in (".html", ".json", ".js", ".css", ".svg"):
            body = path.read_text()
            if re.search(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}", body):
                errors.append(f"Credential material in {path.name}")
    if errors:
        raise ValueError("\n".join(sorted(set(errors))))


def build(receipts=None):
    check_reviews()
    signature = publication_inputs()
    receipts = receipts if receipts is not None else {}
    revision = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=normal"))
    key = digest(json.dumps([signature, receipts, revision, dirty], sort_keys=True).encode())
    output = BUILD / "candidates" / key
    if (output / "manifest.json").exists():
        validate_site(output / "site")
        return output
    output.mkdir(parents=True, exist_ok=True)
    stage = output / "docs"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    data = catalog()
    built_at = datetime.now(timezone.utc).isoformat()
    mapping = dict(data["imports"])
    for component in data["components"]:
        for source in component["pages"]:
            mapping[source] = str(Path(source).relative_to("wiki/content"))
    reviews = json.loads(REVIEWS.read_text())
    for source, destination in mapping.items():
        body = safe_file(source).read_text()
        asset_mapping = {str(p.relative_to(ROOT)): "assets/" + p.name for p in (PROJECT / "assets").iterdir() if p.is_file()}
        body = rewrite_links(body, source, destination, {**mapping, **asset_mapping}, revision)
        owner = next((c for c in data["components"] if source in c["pages"]), None)
        reviewed = reviews[owner["id"]]["reviewed_at"] if owner else "See the dated observations in this runbook"
        committed = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{revision}:{source}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        source_label = f"[Source]({source_url(source, revision)})" if committed else f"Source: `{source}` (new working-tree file)"
        body += (f"\n\n---\n\n{source_label} · "
                 f"Documentation reviewed: {reviewed}.  \nSource revision: `{revision[:12]}`"
                 f"{' + working-tree changes' if dirty else ''}. Built: {built_at}. "
                 "Build time is not a live verification time.\n")
        target = stage / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    shutil.copytree(PROJECT / "assets", stage / "assets")
    export_reference(stage)
    deployment_page = "# Deployment evidence\n\nOnly successful wrapped deployments create these receipts. "
    deployment_page += "An absent component is unverified, not unavailable. Historical observations remain in the runbooks.\n\n"
    deployment_page += table(["Scope", "Completed at (UTC)", "Source revision", "Working tree", "Evidence limit"],
                            [[name, r["completed_at"], r["revision"][:12], r["dirty"], "Deployment command succeeded"]
                             for name, r in sorted(receipts.items())])
    (stage / "reference/deployments.md").write_text(deployment_page)
    config = {
        "site_name": "Smarthome field guide", "site_url": "http://wiki.home.arpa/",
        "docs_dir": str(stage), "site_dir": str(output / "site"),
        "theme": {"name": "mkdocs", "custom_dir": str(PROJECT / "theme"), "locale": "en",
                  "color_mode": "light", "user_color_mode_toggle": False, "analytics": None,
                  "highlightjs": False, "navigation_depth": 3},
        "plugins": [{"search": {"prebuild_index": False}}],
        "markdown_extensions": ["attr_list", "tables", "fenced_code", "toc"],
        "extra_css": ["assets/wiki.css"], "nav": data["nav"],
        "validation": {"links": {"not_found": "warn", "unrecognized_links": "warn", "anchors": "warn"}},
    }
    config_path = output / "mkdocs.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    run([sys.executable, "-m", "mkdocs", "build", "--strict", "-f", str(config_path)])
    # The built-in theme's version notification is an optional external script.
    # Remove it if a later theme version adds one; validation still rejects all other external assets.
    site = output / "site"
    publication = {"revision": revision, "dirty": dirty, "source_fingerprint": signature,
                   "built_at": built_at, "receipts": receipts}
    write_json(site / "publication.json", publication)
    validate_site(site)
    files = {str(p.relative_to(site)): digest(p.read_bytes()) for p in sorted(site.rglob("*")) if p.is_file()}
    release = digest(json.dumps(files, sort_keys=True).encode())
    manifest = {"release": release, "files": files, "publication": publication}
    write_json(output / "manifest.json", manifest)
    print(f"Built {len(files)} static files: {output / 'site'}")
    return output


class WikiHTTPError(ValueError):
    def __init__(self, url, code):
        self.code = code
        super().__init__(f"{url}: unexpected HTTP status {code}")


def fetch_wiki(path):
    """Use the native HTTP client for direct LAN access, independent of Python proxies."""
    url = "http://192.168.1.66" + path
    # Shell environments such as Conda can shadow curl. On macOS use the
    # Apple-provided client whose LAN access was verified in the user's terminal.
    client = "/usr/bin/curl" if sys.platform == "darwin" else "curl"
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / "response"
        result = subprocess.run(
            [client, "--disable", "--silent", "--show-error", "--noproxy", "*",
             "--connect-timeout", "8", "--max-time", "15", "--max-filesize", "1048576",
             "--output", str(body), "--write-out", "%{http_code}", url],
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise ConnectionError(f"{url}: {client} exit {result.returncode}: {result.stderr.strip()}")
        if result.stdout != "200":
            raise WikiHTTPError(url, int(result.stdout))
        return body.read_text()


def existing_receipts():
    try:
        data = json.loads(fetch_wiki("/publication.json"))
        return data.get("receipts", {})
    except WikiHTTPError as e:
        if e.code == 404:
            raise ValueError("Live wiki has no publication metadata; do not discard its evidence") from e
        raise
    except ConnectionError as original:
        # First migration only: positively identify the original guide. An
        # unavailable modern site must never silently lose deployment receipts.
        try:
            body = fetch_wiki(":8090/")
        except (ValueError, OSError, subprocess.SubprocessError) as fallback:
            raise ValueError(f"Cannot read existing wiki receipts: {original}; legacy probe: {fallback}") from original
        if "Usenet field guide" in body and "Smarthome field guide" not in body:
            return {}
        raise ValueError(f"Cannot establish the previous wiki's publication evidence: {original}") from original


def deploy(output):
    manifest = json.loads((output / "manifest.json").read_text())
    validate_site(output / "site")
    actual = {str(p.relative_to(output / "site")): digest(p.read_bytes())
              for p in sorted((output / "site").rglob("*")) if p.is_file()}
    if actual != manifest["files"]:
        raise ValueError("Candidate changed after validation")
    archive = output / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in manifest["files"]:
            bundle.add(output / "site" / name, arcname="site/" + name, recursive=False)
        for name in ("compose.yaml", "Caddyfile", "Dockerfile", ".dockerignore"):
            bundle.add(ROOT / "usenet-infra/wiki" / name, arcname="runtime/" + name, recursive=False)
        bundle.add(PROJECT / "apply.sh", arcname="runtime/apply.sh", recursive=False)
        checksums = "".join(f"{sha}  site/{name}\n" for name, sha in manifest["files"].items())
        for name in ("compose.yaml", "Caddyfile", "Dockerfile", ".dockerignore"):
            checksums += f"{digest((ROOT / 'usenet-infra/wiki' / name).read_bytes())}  runtime/{name}\n"
        checksums += f"{digest((PROJECT / 'apply.sh').read_bytes())}  runtime/apply.sh\n"
        checksum_file = output / "SHA256SUMS"
        checksum_file.write_text(checksums)
        bundle.add(checksum_file, arcname="SHA256SUMS", recursive=False)
    extra = output / "ansible-vars.json"
    write_json(extra, {"qnap_wiki_source_dir": str(output / "site"),
                       "qnap_wiki_manifest": manifest, "qnap_wiki_archive": str(archive),
                       "qnap_wiki_archive_sha256": digest(archive.read_bytes())})
    run(["just", "--justfile", "usenet-infra/Justfile", "--working-directory", "usenet-infra",
         "wiki-publish", str(extra)], cwd=ROOT)


def with_deployment(scopes, command):
    if not command:
        raise ValueError("Missing deployment command")
    if command[0] == "--":
        command = command[1:]
    if scopes == "home-assistant" and command[:2] == ["just", "talos-deploy"]:
        addons = {p.parent.name for p in ROOT.glob("*/addon.yaml") if not yaml.safe_load(p.read_text()).get("disabled")}
        selected = addons if "all" in command[3:] else addons.intersection(command[3:])
        scopes = ",".join(sorted(selected) + ([] if "--skip-config" in command else ["home-assistant-config"]))
    cwd = os.environ.get("WIKI_CALLER_DIR", str(ROOT))
    dry_run = any(arg.startswith("--dry-run") or arg in ("dry-run", "dry-run-verbose") for arg in command)
    dry_run = dry_run or ("ansible-playbook" in command and any(arg in ("--check", "-C") for arg in command))
    informational = any(arg in ("--help", "-h", "--version") for arg in command)
    if os.environ.get("SMARTHOME_WIKI_DEPLOY_ACTIVE") or dry_run or informational:
        return subprocess.call(command, cwd=cwd)
    output = build()
    before = json.loads((output / "manifest.json").read_text())["publication"]
    try:
        existing_receipts()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Wiki preflight failed before services were changed: {error}", file=sys.stderr)
        return 3
    environment = {**os.environ, "SMARTHOME_WIKI_DEPLOY_ACTIVE": "1"}
    result = subprocess.call(command, cwd=cwd, env=environment)
    if result:
        print("Deployment failed; wiki was not published.", file=sys.stderr)
        return result
    pending = BUILD / "pending-receipts.json"
    receipts = json.loads(pending.read_text()) if pending.exists() else {}
    for scope in filter(None, scopes.split(",")):
        receipts[scope] = {"completed_at": datetime.now(timezone.utc).isoformat(),
                           "revision": before["revision"], "dirty": before["dirty"],
                           "source_fingerprint": before["source_fingerprint"]}
    write_json(pending, receipts)
    try:
        if publication_inputs() != before["source_fingerprint"]:
            raise ValueError("Documentation inputs changed during deployment; review before publishing")
        for scope, record in existing_receipts().items():
            if record["completed_at"] > receipts.get(scope, {}).get("completed_at", ""):
                receipts[scope] = record
        # Preserve evidence locally even if publication fails; it never implies a live service probe.
        write_json(BUILD / "pending-receipts.json", receipts)
        deploy(build(receipts))
        (BUILD / "pending-receipts.json").unlink(missing_ok=True)
    except Exception as error:
        print(f"Services deployed successfully, but wiki publication failed: {error}\n"
              "Previous wiki retained. Retry with just wiki-deploy; do not roll back services.", file=sys.stderr)
        return 3
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("build", "check", "preview", "deploy", "rollback"):
        sub.add_parser(action)
    p = sub.add_parser("review")
    p.add_argument("component")
    p.add_argument("reason")
    p = sub.add_parser("with-deployment")
    p.add_argument("--scope", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "review":
        review(args.component, args.reason)
    elif args.action == "with-deployment":
        return with_deployment(args.scope, args.command)
    elif args.action == "rollback":
        run(["just", "--justfile", "usenet-infra/Justfile", "--working-directory", "usenet-infra", "wiki-rollback"], cwd=ROOT)
    elif args.action == "deploy":
        receipts = existing_receipts()
        pending = BUILD / "pending-receipts.json"
        if pending.exists():
            for name, receipt in json.loads(pending.read_text()).items():
                if receipt["completed_at"] > receipts.get(name, {}).get("completed_at", ""):
                    receipts[name] = receipt
        deploy(build(receipts))
        pending.unlink(missing_ok=True)
    else:
        output = build()
        if args.action == "check":
            run([sys.executable, "-m", "unittest", "discover", "-s", "wiki/tests", "-v"], cwd=ROOT)
            run([sys.executable, "-m", "unittest", "discover", "-s", "network-infra/dns", "-p", "test_*.py", "-v"], cwd=ROOT)
        elif args.action == "preview":
            run([sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1", "--directory", str(output / "site")])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
