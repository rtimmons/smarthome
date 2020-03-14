import {Router} from 'express';
import * as sleep from 'sleep';

import {i2c} from './i2c';

interface Relay {
    address: number;
    bit: number;
}

interface PerPosition<T> {
    up: T;
    down: T;
    mid?: T;
}

type BlindState = keyof PerPosition<Relay>;

class Blind {
    relays: PerPosition<Relay>;
    state: BlindState;
    i2c1: any;

    static waits: PerPosition<number> = {
        up: 2,
        down: 2,
        mid: 4,
    };

    constructor(relays: PerPosition<Relay>) {
        this.state = 'up';
        this.relays = relays;
        process.on('exit', () => this.onExit());
        this.i2c1 = i2c.openSync(1);
    }

    onExit() {
        this.i2c1.closeSync();
    }

    setState(state: BlindState) {
        // console.log(`Setting state to ${state} with a sleep of ${GpioBlind.waits[state]}`);
        const relay = this.relays[state];
        const wait = Blind.waits[state];
        //Some blinds do not have mid setting. If null, do nothing.
        if(typeof relay === 'undefined' || typeof wait === 'undefined') {
            return;
        }

        const i2c1 = i2c.openSync(1);
        try {
            i2c1.writeByteSync(relay.address, 0x10, relay.bit);
            sleep.sleep(wait);
            i2c1.writeByteSync(relay.address, 0x10, 0x0);
            this.state = state;
        } finally {
            i2c1.closeSync();
        }

    }
    getState(): {state: BlindState} {
        return {state: this.state};
    }
}

const rooms: {[k: string] : Blind} = {
    bedroom_roller: new Blind({
        up: {address: 0x11, bit: 0x2},
        down: {address: 0x11, bit: 0x1}
    }),
    bedroom_blackout: new Blind({
        up: {address: 0x11, bit: 0x08},
        down: {address: 0x12, bit: 0x04},
        mid: {address: 0x11, bit: 0x04}
    }),
    living_roller: new Blind({
        up: {address: 0x13, bit: 0x02},
        down: {address: 0x13, bit: 0x01}
    }),
    office_roller: new Blind({
        up: {address: 0x12, bit: 0x02},
        down: {address: 0x12, bit: 0x01}
    }),
    office_blackout: new Blind({
        up: {address: 0x13, bit: 0x08},
        down: {address: 0x13, bit: 0x04},
        mid: {address: 0x12, bit: 0x08}
    }),
};

export const blindControli2c = Router();

blindControli2c.get('/blinds-i2c/:room', (req, res) => {
    const room = req.params.room.toLowerCase();
    if (typeof rooms[room] === 'undefined') {
        res.json({error: `unknown room ${room}`});
        return;
    }
    res.json(rooms[room].getState());
});

blindControli2c.post('/blinds-i2c/:room', (req, res) => {
    const room = req.params.room.toLowerCase();
    if (typeof rooms[room] === 'undefined') {
        res.json({error: `unknown room ${room}`});
        return;
    }
    if (typeof req.body.state === 'undefined') {
        res.status(400);
        res.json({error: 'Missing state parameter'});
    } else {
        rooms[room].setState(req.body.state);
        res.json(rooms[room].getState());
    }
});
