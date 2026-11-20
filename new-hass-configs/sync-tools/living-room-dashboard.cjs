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
  const source = (name) => yaml.parse(fs.readFileSync(
    path.resolve(__dirname, "../dashboards", name), "utf8"
  ));
  const card = source("living-room-heating-schedule.yaml");
  const roomView = source("nest-heating-schedules.yaml");
  const view = config.views.find((candidate) => candidate.path === "heating");
  const section = view?.sections?.find((candidate) => candidate.cards?.some(
    (entry) => entry.entity === "climate.living_room"
  ));
  assert(section, "Living Room Climate dashboard has no thermostat section");

  const existing = section.cards.findIndex((entry) => entry.title === card.title);
  const existingRoomView = config.views.findIndex((entry) => entry.path === roomView.path);
  if (existing >= 0 && JSON.stringify(section.cards[existing]) === JSON.stringify(card)
      && existingRoomView >= 0
      && JSON.stringify(config.views[existingRoomView]) === JSON.stringify(roomView)) {
    console.log("Nest dashboard schedules already match");
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
  if (existingRoomView >= 0) {
    config.views[existingRoomView] = roomView;
  } else {
    config.views.push(roomView);
  }
  await ha.callHomeAssistantWs(options, token, {
    type: "lovelace/config/save", url_path, config,
  });
  assert.deepEqual(await readConfig(), config, "Dashboard readback differs");
  console.log("Published Nest dashboard schedules");
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
