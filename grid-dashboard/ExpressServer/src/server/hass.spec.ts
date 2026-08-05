import { expect } from 'chai';

import { fastSceneEntityId } from './hass';

describe('Home Assistant scene routing', () => {
    it('maps dashboard scene paths to fast-scene scripts', () => {
        expect(fastSceneEntityId('scene_living_room_high')).to.equal(
            'script.fast_scene_living_room_high'
        );
        expect(fastSceneEntityId('scene_all_off')).to.equal(
            'script.fast_scene_all_off'
        );
    });

    it('rejects malformed scene paths', () => {
        expect(fastSceneEntityId('living_room_high')).to.equal(undefined);
        expect(fastSceneEntityId('scene_../living_room_high')).to.equal(
            undefined
        );
        expect(fastSceneEntityId('scene_living-room-high')).to.equal(undefined);
    });
});
