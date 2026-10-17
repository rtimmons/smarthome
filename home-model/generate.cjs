const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const source = path.join(__dirname, 'rooms.json');

function unique(values, label) {
  if (values.some(value => typeof value !== 'string' || !value) ||
      new Set(values).size !== values.length) {
    throw new Error(`Expected unique, nonempty ${label}`);
  }
}

function validate(model) {
  unique(model.areas.map(area => area.id), 'area IDs');
  unique(model.areas.map(area => area.name), 'area names');
  unique(model.rooms.map(room => room.id), 'room IDs');
  unique(model.rooms.map(room => room.name), 'room names');
  unique(model.rooms.map(room => room.sonosEntityId), 'Sonos entities');
  unique(model.groupAllOrder, 'group-all room IDs');
  const areas = new Map(model.areas.map(area => [area.id, area]));
  for (const room of model.rooms) {
    const area = areas.get(room.areaId);
    if (!area || (!room.portable && area.name !== room.name)) {
      throw new Error(`Room ${room.id} must map to a matching physical area`);
    }
    if (!/^media_player\.[a-z0-9_]+$/.test(room.sonosEntityId) ||
        !/^[a-z0-9_]+$/.test(room.lightingSceneRoom) ||
        (room.temperatureEntityId !== null && !/^(climate|weather)\.[a-z0-9_]+$/.test(room.temperatureEntityId)) ||
        typeof room.portable !== 'boolean' || !room.emojiName) {
      throw new Error(`Invalid room controls: ${room.id}`);
    }
  }
  if (model.groupAllOrder.length !== model.rooms.length ||
      model.groupAllOrder.some(id => !model.rooms.some(room => room.id === id))) {
    throw new Error('Group-all order must contain every dashboard room exactly once');
  }
  return model;
}

function outputs(model = JSON.parse(fs.readFileSync(source, 'utf8'))) {
  validate(model);
  const header = '// Generated from home-model/rooms.json by just rooms-generate. Do not edit.\n';
  return {
    'grid-dashboard/ExpressServer/src/public/js/room-catalog.js':
      header + 'const homeRooms = ' + JSON.stringify(model, null, 4) + ';\n\n' +
      "if (typeof module !== 'undefined' && module.exports) {\n    module.exports = homeRooms;\n}\n",
    'sonos-api/src/server/room-catalog.ts':
      header + 'export const SONOS_ROOM_TO_ENTITY = ' +
      JSON.stringify(Object.fromEntries(model.rooms.map(room => [room.name, room.sonosEntityId])), null, 2) +
      ' as const;\n',
  };
}

function check() {
  for (const [file, content] of Object.entries(outputs())) {
    if (!fs.existsSync(path.join(root, file)) || fs.readFileSync(path.join(root, file), 'utf8') !== content) {
      throw new Error(`${file} is stale; run just rooms-generate`);
    }
  }
}

if (require.main === module) {
  if (process.argv.includes('--check')) {
    check();
    console.log('Shared room definitions are current.');
  } else {
    for (const [file, content] of Object.entries(outputs())) {
      fs.writeFileSync(path.join(root, file), content);
      console.log(`Generated ${file}`);
    }
  }
}

module.exports = { validate, outputs, check };
