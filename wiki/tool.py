"""Allowlisted static documentation and deployment transactions. Never queries HA state."""
from __future__ import annotations

import argparse
from collections import Counter
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
from areas import render_rooms

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "wiki"
BUILD = ROOT / "build/wiki"
CATALOG = PROJECT / "components.json"
REVIEWS = PROJECT / "reviews.json"
REPO_URL = "https://github.com/rtimmons/smarthome/blob/"
PRIVATE_REPOSITORIES = ("printer",)


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


def private_repository(path):
    return next((name for name in PRIVATE_REPOSITORIES if path.startswith(name + "/")), None)


def known_source_files(root=ROOT):
    # Git's tracked-file list prevents ignored secrets and local runtime artifacts
    # from becoming review inputs. Only explicitly named nested repos participate.
    known = set(subprocess.check_output(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"], text=True).splitlines())
    known = {p for p in known if not private_repository(p)}
    for name in PRIVATE_REPOSITORIES:
        nested = root / name
        if (nested / ".git").exists():
            paths = subprocess.check_output(["git", "-C", str(nested), "ls-files", "--cached", "--others", "--exclude-standard"], text=True).splitlines()
            known.update(f"{name}/{p}" for p in paths)
    return known


def source_files(component, root=ROOT):
    known = known_source_files(root)
    import fnmatch
    matched = set(component.get("pages", []) + component.get("runbooks", []))
    for pattern in component["watch"]:
        matches = {p for p in known if fnmatch.fnmatchcase(p, pattern) and (root / p).is_file()}
        if not matches:
            raise ValueError(f"{component['id']}: watched source matches no files: {pattern}")
        matched.update(matches)
    return sorted(matched)


def fingerprint(paths, root=ROOT):
    return digest(json.dumps({p: digest(safe_file(p, root).read_bytes()) for p in sorted(set(paths))},
                             sort_keys=True).encode())


def catalog():
    data = json.loads(CATALOG.read_text())
    data["imports"] = {source: "runbooks/" + source for c in data["components"] for source in c.get("runbooks", [])}
    return data


def check_catalog(data):
    components = data["components"]
    for label, values in (
        ("component", [c["id"] for c in components]),
        ("page", [p for c in components for p in c["pages"] + c.get("runbooks", [])]),
        ("add-on", [a for c in components for a in c.get("addons", [])]),
    ):
        duplicates = sorted(key for key, count in Counter(values).items() if count > 1)
        if duplicates:
            raise ValueError(f"Duplicate {label} ownership: {duplicates}")
    expected = {str(p.relative_to(ROOT)) for p in (PROJECT / "content").rglob("*.md")}
    actual = {p for c in components for p in c["pages"]}
    if expected != actual:
        raise ValueError(f"Guide coverage differs: {sorted(expected ^ actual)}")
    for source in [p for c in components for p in c["pages"] + c.get("runbooks", [])]:
        safe_file(source)


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
    check_catalog(data)


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
    if private_repository(path):
        raise ValueError(f"Private source cannot be linked to GitHub: {path}")
    return REPO_URL + revision + "/" + quote(path, safe="/")


def source_reference(path, revision, label=None):
    if private_repository(path):
        return f"{label or f'`{path}`'} (private {private_repository(path)} repository)"
    return f"[{label or path}]({source_url(path, revision)})"


def private_repository_states():
    states = {}
    for name in PRIVATE_REPOSITORIES:
        path = ROOT / name
        revision = subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
                                  capture_output=True, text=True)
        states[name] = {
            "revision": revision.stdout.strip() if revision.returncode == 0 else None,
            "dirty": bool(subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=normal"], text=True).strip()),
        }
    return states


def table(headers, rows):
    def cell(x):
        return escape(str(x)).replace("|", "&#124;").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                      *["| " + " | ".join(cell(x) for x in row) + " |" for row in rows]]) + "\n"


REFERENCE_PAGES = {
    "Overview": "index.md", "Services": "services.md", "Rooms and areas": "rooms.md", "Devices": "devices.md",
    "Scenes": "scenes.md", "Controls and automations": "controls.md", "DNS policy": "network.md",
    "Documentation coverage": "coverage.md", "Deployment evidence": "deployments.md",
}


def page_title(source):
    match = re.search(r"^# (.+)$", safe_file(source).read_text(), re.M)
    if not match:
        raise ValueError(f"Page needs a title: {source}")
    return match[1].strip()


def navigation(data):
    def guides(component):
        return [{page_title(p): str(Path(p).relative_to("wiki/content"))} for p in component["pages"]]
    by_id = {c["id"]: c for c in data["components"]}
    return [{"Start here": "index.md"},
            {"Household": [item for key in ("dashboard", "lighting", "audio", "integrations", "printing", "utilities")
                           for item in guides(by_id[key])]},
            {"Media": guides(by_id["media"])}, {"Network": "network.md"},
            {"Maintenance": "maintenance.md"},
            {"Reference": [{title: "reference/" + path} for title, path in REFERENCE_PAGES.items()]},
            {"Runbooks": "runbooks/index.md"}]


def export_reference(stage, data, revision):
    # Execute the model in its existing pinned Node/TypeScript environment.
    run(["just", "wiki-model-export"], cwd=ROOT)
    model = json.loads((BUILD / "model.json").read_text())
    def source_link(source):
        return source_reference(source, revision)

    def generated(name, title, sources, body):
        target = stage / "reference" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {title}\n\nGenerated at build time from {', '.join(source_link(s) for s in sources)}. "
                          "This is repository configuration, not live state or deployment evidence.\n\n" + body)

    services = []
    for path in sorted(ROOT.glob("*/addon.yaml")):
        addon = yaml.safe_load(path.read_text())
        services.append([addon["name"], path.parent.name,
                         "disabled / retained" if addon.get("disabled") else "enabled",
                         "yes" if addon.get("ingress") else "no",
                         "host" if addon.get("host_network") else "container",
                         ", ".join(f"{p} → {host if host is not None else 'unmapped'}" for p, host in addon.get("ports", {}).items()) or "—",
                         ", ".join(addon.get("depends_on", [])) or "—"])
    generated("services.md", "Services", [str(p.relative_to(ROOT)) for p in sorted(ROOT.glob("*/addon.yaml"))],
              "Ports show container → configured host mappings. Supervisor options and firewall rules can change actual access. "
              "A declared host mapping is not add-on-only isolation. Dependencies list manifest build/deploy ordering; "
              "external devices and Home Assistant integrations are described in the guides.\n\n" +
              table(["Service", "Source directory", "Desired status", "HA sidebar", "Network", "Ports", "Dependencies"], services))
    generated("rooms.md", "Rooms and device areas", ["home-model/rooms.json", "home-model/device-catalog.json", "home-model/area-verification.json", "home-model/speaker-name-verification.json"], render_rooms(model, table))
    area_names = {a["id"]: a["name"] for a in model.get("rooms", {}).get("areas", [])}
    generated("devices.md", "Lighting device catalog", ["new-hass-configs/config-generator/src/devices.ts", "new-hass-configs/config-generator/src/scenes.ts", "docs/operations/zwave-product-catalog.json"],
              "[Browse all devices by physical room](rooms.md), including speakers, climate, sensors and unconfirmed locations. "
              "This table lists the logical lighting targets and wall-switch aliases. Physical area never expands a scene's target list.\n\n" +
              "Logical names can alias the same entity. All-off membership below comes from the actual scene generator, "
              "including its blocklist, diagnostic-endpoint and scene-exclusion rules. An inventory removal marker alone "
              "does not remove a declared scene target; live health filtering still runs during dispatch.\n\n" +
              table(["Physical area", "Logical name", "Entity", "Type", "Inventory", "Scene status", "In generated all-off", "Scene off permitted"],
                    [[area_names.get(d.get("areaId"), "Unassigned"), d["key"], d["entity"], d["type"], d["inventoryStatus"], d["sceneStatus"],
                      "yes" if d["effectiveAllOff"] else "no", "yes" if d["allowSceneTurnOff"] else "no"] for d in sorted(model["devices"], key=lambda d: (d.get("areaId") or "", d["key"]))]) +
              "\n## Hardware product references\n\nArea names are checked against the physical catalog.\n\n" +
              table(["Manufacturer / product", "Entity", "Physical area"],
                    [[p["manufacturer"] + " / " + p["label"], r["entityId"], area_names.get(r["areaId"], "Unassigned")]
                     for p in model.get("products", []) for r in p["references"]]))
    scene_body = "Use these fast-scene scripts for operation. Targets and desired states use the same generator as deployment, "
    scene_body += "after static exclusions and entity deduplication, before live health/mismatch filtering. Brightness is 0–255.\n\n"
    scene_body += "\n".join(f"- [{s['name']}](#{s['id'].replace('_', '-')})" for s in model["scenes"]) + "\n\n"
    for scene in model["scenes"]:
        scene_body += f"## {scene['name']} {{#{scene['id'].replace('_', '-')}}}\n\n`{scene['script']}`\n\n"
        scene_body += table(["Logical name", "Entity", "Desired state"],
                            [[t["device"], t["entity"], json.dumps(t["state"], sort_keys=True)] for t in scene["targets"]])
        if scene["omitted"]:
            scene_body += "\nDeclared names omitted by exclusion or entity deduplication: " + ", ".join(f"`{s}`" for s in scene["omitted"]) + ".\n"
        scene_body += "\n"
    generated("scenes.md", "Scenes and rooms", ["new-hass-configs/config-generator/src/scenes.ts", "new-hass-configs/config-generator/src/scene-generation.ts"], scene_body)
    generated("controls.md", "Controls and automations", ["new-hass-configs/config-generator/src/automations.ts", "new-hass-configs/config-generator/src/automation-generation.ts"],
              "This table covers the TypeScript registry. Webhook identifiers and action payloads are deliberately omitted. "
              "Mode is the generated mode: interactive scene callers use restart even when a definition says single. "
              "Manual YAML, package and UI-owned automations are outside this table; see the climate and maintenance guides.\n\n" +
              table(["Control", "Trigger", "Action", "Conditions", "Effective mode"],
                    [[a["name"], "; ".join(a["triggers"]), "; ".join(a["actions"]),
                      "see source" if a["conditional"] else "none", a["mode"]] for a in model["controls"]]))
    policy = json.loads(safe_file("network-infra/dns/policy.json").read_text())
    service_source = "docs/operations/service-hostnames.md"
    service_body = safe_file(service_source).read_text().split("\n", 1)[1].lstrip()
    service_body = rewrite_links(service_body, service_source, "reference/network.md", data["imports"], revision)
    # Include the canonical authored explanation and dated evidence without a
    # second route inventory to maintain. Nest its sections under this page.
    service_body = re.sub(r"^(#{2,5}) ", r"#\1 ", service_body, flags=re.M)
    generated("network.md", "DNS policy", ["network-infra/dns/policy.json", service_source],
              "Client DHCP adoption and gateway migration remain dated operational decisions in the [network guide](../network.md). "
              "This policy does not establish which resolvers a client is using.\n\n" +
              table(["Setting", "Configured value"], [["Local zone", policy["zone"]], ["Resolvers", ", ".join(policy["resolvers"])],
                    ["Local record owner", policy["record_owner"]], ["Trusted-client resolver", policy["client_resolver"]],
                    ["Gateway domain forwarding", policy["gateway_forwarding"]["zone"] + " → " + ", ".join(policy["gateway_forwarding"]["resolvers"])],
                    ["Duplicate native wiki A enabled", policy["gateway_forwarding"]["native_wiki_a_enabled"]],
                    ["Upstreams", ", ".join(policy["upstream_dns"])], ["Fallbacks", ", ".join(policy["fallback_dns"]) or "none"]]) +
              "\n## HTTP service routing\n\n"
              "The following explanation and dated acceptance come from the "
              "[service hostname runbook](../runbooks/docs/operations/service-hostnames.md). "
              "Rebuilding this page does not refresh those observations.\n\n" + service_body +
              "\n## Local records\n\n" + table(["Name", "Address"], sorted(policy["records"].items())) +
              "\n## Filter policy\n\n" + table(["Filter", "Enabled"], [[f["name"], f["enabled"]] for f in policy["filters"]]))
    reviews = json.loads(REVIEWS.read_text())
    coverage = "Every guide and imported runbook has one component owner. Changes to either, or to its watched sources, require review. "
    coverage += "A review records a human/agent assessment of documentation; it is not a hardware acceptance test.\n\n"
    runbooks = "# Technical runbooks\n\nCanonical repository guides, copied into this site at build time. "
    runbooks += "Dated observations retain their original limits. [Household tasks](../index.md) are the starting point for everyday use.\n\n"
    for component in data["components"]:
        coverage += f"## {component['title']}\n\n"
        for source in component["pages"]:
            coverage += f"- [{page_title(source)}](../{Path(source).relative_to('wiki/content')})\n"
        record = reviews[component["id"]]
        coverage += f"\nReviewed: {record['reviewed_at']}. Reason: {escape(record['reason'])}\n\n"
        coverage += f"{len(source_files(component))} source files; {len(component.get('runbooks', []))} imported runbooks.\n\n"
        coverage += "Watched sources: " + ", ".join(f"`{p}`" for p in component["watch"]) + ".\n\n"
        if component.get("runbooks"):
            runbooks += f"## {component['title']}\n\n"
            for source in component["runbooks"]:
                runbooks += f"- [{page_title(source)}]({source})\n"
            runbooks += "\n"
    generated("coverage.md", "Documentation coverage", ["wiki/components.json", "wiki/reviews.json"], coverage)
    (stage / "runbooks/index.md").write_text(runbooks)
    generated("index.md", "Repository configuration", ["wiki/components.json"],
              f"{len(services)} add-ons · {len(model['devices'])} logical device entries · {len(model['scenes'])} scenes · "
              f"{len(model['controls'])} generated automations · {len(data['imports'])} imported runbooks.\n\n" +
              "\n".join(f"- [{title}]({path})" for title, path in REFERENCE_PAGES.items() if path != "index.md") +
              "\n\n## Services\n\n[Service settings and dependencies](services.md).\n\n## Devices\n\n[Device inventory and all-off membership](devices.md).\n\n"
              "## Scenes and rooms\n\n[Effective scene targets](scenes.md) and [controls](controls.md).\n\n"
              "## Build runtimes\n\n" + table(["Runtime", "Repository pin"], [["Node", safe_file(".nvmrc").read_text().strip()],
                                                                           ["Python", safe_file(".python-version").read_text().strip()]]))


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
        parsed = urlsplit(reference)
        if parsed.scheme == "wiki-reference":
            filename = "index.md" if parsed.path == "inventory" else parsed.path + ".md"
            if filename not in REFERENCE_PAGES.values():
                raise ValueError(f"Unknown generated reference: {reference}")
            result = os.path.relpath("reference/" + filename, Path(destination).parent)
            return prefix + result + ("#" + parsed.fragment if parsed.fragment else "") + suffix
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
            if private_repository(relative):
                if relative not in known_source_files():
                    raise ValueError(f"Unpublished local link in {source}: {reference}")
                safe_file(relative)
                return source_reference(relative, revision, prefix[1:-2])
            if subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", relative],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                raise ValueError(f"Unpublished local link in {source}: {reference}")
            result = source_url(relative, revision)
            if parsed.fragment:
                result += "#" + parsed.fragment
        return prefix + result + suffix
    return re.sub(r"(\[[^\]\n]*\]\()([^\s)]+)(\))", replace, text)


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
    private_states = private_repository_states()
    dirty = bool(git("status", "--porcelain", "--untracked-files=normal")) or any(s["dirty"] for s in private_states.values())
    key = digest(json.dumps([signature, receipts, revision, dirty, private_states], sort_keys=True).encode())
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
        owner = next((c for c in data["components"] if source in c["pages"] + c.get("runbooks", [])), None)
        reviewed = reviews[owner["id"]]["reviewed_at"] if owner else "See the dated observations in this runbook"
        committed = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{revision}:{source}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if private_repository(source):
            state = private_states[private_repository(source)]
            source_label = source_reference(source, revision) + f" · Private revision: `{state['revision'] or 'uncommitted'}`"
        else:
            source_label = source_reference(source, revision, "Source") if committed else f"Source: `{source}` (new working-tree file)"
        body += (f"\n\n---\n\n{source_label} · "
                 f"Documentation reviewed: {reviewed}.  \nSource revision: `{revision[:12]}`"
                 f"{' + working-tree changes' if dirty else ''}. Built: {built_at}. "
                 "Build time is not a live verification time.\n")
        target = stage / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    shutil.copytree(PROJECT / "assets", stage / "assets")
    export_reference(stage, data, revision)
    deployment_page = "# Deployment evidence\n\nOnly successful wrapped deployments create these receipts. "
    deployment_page += "An absent component is unverified, not unavailable. Historical observations remain in the runbooks.\n\n"
    deployment_page += table(["Scope", "Completed at (UTC)", "Source revision", "Working tree", "Evidence limit"],
                            [[name, r["completed_at"], r["revision"][:12], r["dirty"], "Deployment command succeeded"]
                             for name, r in sorted(receipts.items())])
    (stage / "reference/deployments.md").write_text(deployment_page)
    for path in [*(stage / "reference").glob("*.md"), stage / "runbooks/index.md"]:
        with path.open("a") as page:
            page.write(f"\n\n---\n\nSource revision: `{revision[:12]}`"
                       f"{' + working-tree changes' if dirty else ''}. Built: {built_at}. "
                       "Build time is not a live verification time.\n")
    config = {
        "site_name": "Smarthome field guide", "site_url": "https://wiki.home.rytim.com/",
        "docs_dir": str(stage), "site_dir": str(output / "site"),
        "theme": {"name": "mkdocs", "custom_dir": str(PROJECT / "theme"), "locale": "en",
                  "color_mode": "light", "user_color_mode_toggle": False, "analytics": None,
                  "highlightjs": False, "navigation_depth": 3},
        "plugins": [{"search": {"prebuild_index": False}}],
        "markdown_extensions": ["attr_list", "tables", "fenced_code", "toc", "def_list"],
        "extra_css": ["assets/wiki.css"], "nav": navigation(data),
        "validation": {"links": {"not_found": "warn", "unrecognized_links": "warn", "anchors": "warn"}},
    }
    config_path = output / "mkdocs.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    run([sys.executable, "-m", "mkdocs", "build", "--strict", "-f", str(config_path)])
    # The built-in theme's version notification is an optional external script.
    # Remove it if a later theme version adds one; validation still rejects all other external assets.
    site = output / "site"
    publication = {"revision": revision, "dirty": dirty, "private_repositories": private_states, "source_fingerprint": signature,
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
