import * as assert from 'node:assert/strict';
import { SONOS_ROOM_TO_ENTITY, requireSonosRoomName } from './sonos-room-map';

const { check } = require('../../../home-model/generate.cjs');
check();
assert.equal(SONOS_ROOM_TO_ENTITY.Move, 'media_player.move');
assert.equal(Object.keys(SONOS_ROOM_TO_ENTITY).length, 8);
assert.throws(() => requireSonosRoomName('Maker Room'), /Unknown Sonos room/);
assert.throws(() => requireSonosRoomName('Outdoor'), /Unknown Sonos room/);
console.log('Shared room catalog preserves the Sonos allowlist.');
