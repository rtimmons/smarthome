import { expect } from 'chai';
import * as fs from 'node:fs';
import * as vm from 'node:vm';
import * as path from 'node:path';
import { thermostatEntityId } from '../../server/hass';

const { check, validate } = require('../../../../../home-model/generate.cjs');
const catalog = require('./room-catalog');

describe('shared home rooms', () => {
    it('ships current generated definitions for both services', () => check());

    it('loads the catalog before configuration in the browser and preserves controls', () => {
        const context = vm.createContext({});
        const html = fs.readFileSync(path.resolve(__dirname, '../index.html'), 'utf8');
        expect(html.indexOf('js/room-catalog.js')).to.be.greaterThan(-1);
        expect(html.indexOf('js/room-catalog.js')).to.be.lessThan(html.indexOf('js/config.js'));
        for (const file of ['room-catalog.js', 'config.js']) {
            vm.runInContext(fs.readFileSync(path.resolve(__dirname, file), 'utf8'), context);
        }
        const config = JSON.parse(vm.runInContext('JSON.stringify(config)', context));
        expect(config.rooms).to.deep.equal([
            'Living Room', 'Bedroom', 'Kitchen', 'Bathroom', 'Office', 'Guest Bathroom', 'Closet', 'Move',
        ]);
        expect(config.cells.filter((cell: any) => cell.activeWhenRoom).map((cell: any) => cell.activeWhenRoom))
            .to.deep.equal(['Bathroom', 'Closet', 'Bedroom', 'Move', 'Kitchen', 'Living Room', 'Guest Bathroom', 'Office']);
        expect(config.lightSceneRooms.Move).to.equal('outdoor');
        expect(thermostatEntityId('Move')).to.equal('weather.forecast_home');
        expect(thermostatEntityId('Bathroom')).to.equal(undefined);
        expect(thermostatEntityId('constructor')).to.equal(undefined);
        const move = catalog.rooms.find((room: any) => room.id === 'move');
        expect(move.portable).to.equal(false);
        expect(catalog.areas.find((area: any) => area.id === move.areaId).name).to.equal('Patio');
        const undocumented = structuredClone(catalog);
        delete undocumented.rooms.find((room: any) => room.id === 'move').areaNameException;
        expect(() => validate(undocumented)).to.throw('document its name exception');
    });

    it('rejects a fixed room mapped to the wrong physical area', () => {
        const invalid = structuredClone(catalog);
        invalid.rooms[0].areaId = 'office';
        expect(() => validate(invalid)).to.throw('matching physical area');
    });
});
