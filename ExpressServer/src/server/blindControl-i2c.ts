import {Router} from 'express';
import * as i2c from 'i2c-bus';
import {Gpio} from 'onoff';
import * as sleep from 'sleep';
import {I2cBus} from "i2c-bus";

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

interface Blind {
    setState(state: BlindState): void;
    getState(): {state: BlindState};
}

class NopBlind implements Blind {
    state: BlindState;
    constructor() {
        this.state = 'up';
    }

    getState(): { state: BlindState } {
        return {state: this.state};
    }

    setState(state: BlindState): void {
        const wait = I2cBlind.waits[state];
        console.log(`Setting state to ${state} with a wait of ${wait}`);
        this.state = state;
    }
}

class I2cBlind implements Blind {
    relays: PerPosition<Relay>;
    state: BlindState;
    i2c1: I2cBus;

    static waits: PerPosition<number> = {
        up: 2,
        down: 2,
        mid: 4,
    };

    constructor(relays: PerPosition<Relay>) {
        this.state = 'up';
        this.relays = relays;
        process.on('SIGINT', () => this.onExit());
        this.i2c1 = i2c.openSync(1);
    }

    onExit() {
        this.i2c1.closeSync();
    }

    setState(state: BlindState) {
        // console.log(`Setting state to ${state} with a sleep of ${GpioBlind.waits[state]}`);
        const relay = this.relays[state];
        const wait = I2cBlind.waits[state];
        //Some blinds do not have mid setting. If null, do nothing.
        if(typeof relay === 'undefined' || typeof wait === 'undefined') {
            return;
        }

        const i2c1 = i2c.openSync(1);
        i2c1.writeByteSync(relay.address, 0x10, relay.bit);
        sleep.sleep(wait);
        i2c1.writeByteSync(relay.address, 0x10, 0x0);
        this.state = state;
        i2c1.closeSync();

    }
    getState(): {state: BlindState} {
        return {state: this.state};
    }
}
export const blindControli2c = Router();

function createBlind(pins: PerPosition<Relay>): Blind {
    return Gpio.accessible ? new I2cBlind(pins) : new NopBlind();
}

const rooms: {[k: string] : Blind} = {
    bedroom_roller: createBlind({
        up: {address: 0x11, bit: 0x2},
        down: {address: 0x11, bit: 0x1}
    }),
    bedroom_blackout: createBlind({
        up: {address: 0x11, bit: 0x08},
        down: {address: 0x12, bit: 0x04},
        mid: {address: 0x11, bit: 0x04}
    }),
    living_roller: createBlind({
        up: {address: 0x13, bit: 0x02},
        down: {address: 0x13, bit: 0x01}
    }),
    office_roller: createBlind({
        up: {address: 0x12, bit: 0x02},
        down: {address: 0x12, bit: 0x01}
    }),
    office_blackout: createBlind({
        up: {address: 0x13, bit: 0x08},
        down: {address: 0x13, bit: 0x04},
        mid: {address: 0x12, bit: 0x08}
    }),
};

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
