"""Render reviewed area metadata. No live network or raw inventory access."""
from html import escape


def render_rooms(model, table):
    rooms = model.get("rooms", {"areas": [], "rooms": []})
    catalog = model.get("placements", {"devices": [], "entities": [], "retired": []})
    names = {a["id"]: a["name"] for a in rooms["areas"]}
    body = "Physical device areas are separate from dashboard selections and scene targets. "
    body += "Each device row uses one stable entity as its anchor; **every entity attached to that device inherits its area**, "
    body += "including disabled and diagnostic entities. Listed related entities are lighting aliases, not extra devices. "
    body += "See [how to confirm or correct a location](../rooms.md) and [lighting targets and power protections](devices.md).\n\n"
    body += " · ".join(f"[{a['name']}](#{a['id']})" for a in rooms["areas"])
    body += " · [Unassigned / unconfirmed](#unassigned) · [Retired](#retired)\n\n"
    verification = model.get("verification")
    if verification:
        body += "## Last registry verification\n\n"
        body += f"Checked **{escape(verification['verifiedAt'])}**: {verification['coveredDevices']} cataloged live devices and "
        body += f"{verification['coveredEntities']} entities. This checked location metadata, not availability or physical operation. "
        body += f"{verification['devicesWithoutEntities']} shared bridge devices have no entities and remain unassigned.\n\n"
        if not verification.get("catalogMatches"):
            body += "**The catalog has changed since this check. These totals describe the previous mapping; rerun the area audit.**\n\n"
        body += table(["Area at check", "Devices", "Entities (including disabled)", "Disabled entities"],
                      [[names.get(a["areaId"], "Unassigned"), a["devices"], a["entities"], a["disabledEntities"]] for a in verification["areas"]]) + "\n"
    else:
        body += "No dated registry verification is recorded yet.\n\n"
    speakers = model.get("speakerVerification")
    if speakers:
        body += "## Sonos and Home Assistant name agreement {#speaker-names}\n\n"
        body += f"Read directly from speaker descriptions and Home Assistant on **{escape(speakers['verifiedAt'])}**. "
        body += "An unreachable speaker is unverified, even if its saved Home Assistant name matches. Names and physical areas are checked against their separate catalog fields.\n\n"
        if not speakers.get("catalogMatches"):
            body += "**The room or device catalog changed after this check; rerun `just rooms-verify --record-verification`.**\n\n"
        outcomes = {"matches": "Matches", "speaker_unreachable": "Speaker unreachable; HA matches", "mismatch": "Mismatch — review required"}
        body += table(["Expected name", "Sonos speaker reports", "HA player / device name", "HA physical area", "Result"],
                      [[s["expectedName"], s["sonosName"] or "Not verified", (s["homeAssistantName"] or "Missing") + " / " + (s["homeAssistantDeviceName"] or "Missing"),
                        s["areaName"] or "Unassigned", outcomes[s["status"]]] for s in speakers["speakers"]]) + "\n"
    body += "## Dashboard mapping\n\n"
    body += table(["Selection", "Physical area / context", "Sonos entity", "Lighting family", "Temperature"],
                  [[r["name"], names[r["areaId"]] + (" (control context; speaker portable)" if r["portable"] else ""),
                    r["sonosEntityId"], r["lightingSceneRoom"], r["temperatureEntityId"] or "None"] for r in rooms["rooms"]]) + "\n"
    for room in rooms["rooms"]:
        if room.get("areaNameException"):
            body += escape(room["areaNameException"]) + "\n\n"
    for area in rooms["areas"]:
        body += f"## {area['name']} {{#{area['id']}}}\n\n"
        body += f"Stable area ID: `{area['id']}`. "
        if not any(r["areaId"] == area["id"] for r in rooms["rooms"]):
            body += "No dashboard tile; this remains a physical area. "
        body += "\n\n"
        records = [d for d in catalog["devices"] if d["areaId"] == area["id"]]
        body += table(["Device / model", "Anchor entity", "Placement / notes"],
                      [[d["name"] + (f" ({d['model']})" if d.get("model") else ""), d["entityId"],
                        ("Temporarily removed. " if d["status"] == "temporarily_removed" else "") + d["note"]] for d in records]) + "\n"
        related = [(d["entityId"], e) for d in records for e in d.get("relatedEntityIds", [])]
        if related:
            body += details("Additional lighting entities on these devices", [f"{e} — same device as {anchor}" for anchor, e in related])
        logical = {d["entity"] for d in model["devices"] if d.get("areaId") == area["id"]}
        scenes = [s for s in model["scenes"] if any(t["entity"] in logical for t in s["targets"])]
        if scenes:
            body += "Lighting presets that reach this area (including cross-room presets): "
            body += ", ".join(f"[{s['name']}](scenes.md#{s['id'].replace('_', '-')})" for s in scenes) + ".\n\n"
        helpers = [e for e in catalog["entities"] if e["areaId"] == area["id"]]
        if helpers:
            body += details(f"Room controls and helpers ({len(helpers)})", [f"{e['entityId']} — {e['note']}" for e in helpers])
    body += "## Unassigned {#unassigned}\n\n"
    for status, title in [("portable", "Portable"), ("unconfirmed", "Location unconfirmed"), ("whole_home", "Shared services and infrastructure")]:
        body += f"### {title}\n\n"
        records = [d for d in catalog["devices"] + catalog["entities"] if d["status"] == status]
        body += table(["Name / entity", "Anchor entity", "Reason"], [[d.get("name", d["entityId"]), d["entityId"], d["note"]] for d in records]) + "\n"
    body += "## Retired {#retired}\n\n"
    body += table(["Retired item", "Former entity", "Decision"], [[d["name"], d["entityId"], d["note"]] for d in catalog["retired"]])
    return body


def details(title, lines):
    # Native HTML details keeps long helper lists browsable without JavaScript.
    return (f"<details><summary>{escape(title)}</summary>\n<ul>\n" +
            "\n".join(f"<li><code>{escape(line.split(' — ')[0])}</code> — {escape(line.split(' — ', 1)[1])}</li>" for line in lines) +
            "\n</ul>\n</details>\n\n")
