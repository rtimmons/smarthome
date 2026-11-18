const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const yaml = require("../config-generator/node_modules/yaml");
const ha = require("../config-generator/dist/cli/home-assistant-client");

async function main() {
  const options = {
    host: process.env.HASS_HOST ?? ha.DEFAULT_HASS_HOST,
    server: process.env.HASS_SERVER ?? ha.DEFAULT_HASS_SERVER,
  };
  const token = ha.getAccessToken(options);
  const url_path = "living-room-climate";
  const readConfig = () => ha.callHomeAssistantWs(options, token, {
    type: "lovelace/config", url_path, force: true,
  });
  const config = await readConfig();
  const card = yaml.parse(fs.readFileSync(
    path.resolve(__dirname, "../dashboards/living-room-heating-schedule.yaml"),
    "utf8"
  ));
  const view = config.views.find((candidate) => candidate.path === "heating");
  const section = view?.sections?.find((candidate) => candidate.cards?.some(
    (entry) => entry.entity === "climate.living_room"
  ));
  assert(section, "Living Room Climate dashboard has no thermostat section");

  const existing = section.cards.findIndex((entry) => entry.title === card.title);
  if (existing >= 0 && JSON.stringify(section.cards[existing]) === JSON.stringify(card)) {
    console.log("Living-room dashboard schedule already matches");
    return;
  }

  const backupDir = path.resolve(__dirname, "../inventory_snapshots/dashboard-backups");
  fs.mkdirSync(backupDir, { recursive: true, mode: 0o700 });
  fs.writeFileSync(
    path.join(backupDir, `living-room-climate-${Date.now()}.json`),
    `${JSON.stringify(config, null, 2)}\n`,
    { mode: 0o600, flag: "wx" }
  );
  if (existing >= 0) {
    section.cards[existing] = card;
  } else {
    section.cards.splice(1, 0, card);
  }
  await ha.callHomeAssistantWs(options, token, {
    type: "lovelace/config/save", url_path, config,
  });
  assert.deepEqual(await readConfig(), config, "Dashboard readback differs");
  console.log("Published living-room dashboard schedule");
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
