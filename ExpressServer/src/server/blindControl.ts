import {Router} from 'express';
import {Gpio} from 'onoff';
import * as sleep from 'sleep';

interface PerPosition<T> {
    up: T;
    down: T;
    mid: T;
}

type BlindState = keyof PerPosition<Gpio>;

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
        const wait = GpioBlind.waits[state];
        console.log(`Setting state to ${state} with a wait of ${wait}`);
        sleep.sleep(wait);
        this.state = state;
    }
}

class GpioBlind implements Blind {
    pins: PerPosition<Gpio>;
    state: BlindState;

    static waits: PerPosition<number> = {
        up: 1,
        down: 1,
        mid: 4,
    };

    constructor(inPins: PerPosition<number>) {
        this.state = 'up';
        this.pins = {
            // Couldn't find a wa to map `new Gpio` over `inPins` values.
            up: new Gpio(inPins.up, 'in'),
            down: new Gpio(inPins.down, 'in'),
            mid: new Gpio(inPins.mid, 'in'),
        };
        process.on('SIGINT', () => this.onExit());
    }

    onExit() {
        this.pins.up.unexport();
        this.pins.down.unexport();
        this.pins.mid.unexport();
    }

    setState(state: BlindState) {
        // console.log(`Setting state to ${state} with a sleep of ${GpioBlind.waits[state]}`);
        this.pins[state].writeSync(1);
        sleep.sleep(GpioBlind.waits[state]);
        this.pins[state].writeSync(0);
        this.state = state;
    }
    getState(): {state: BlindState} {
        return {state: this.state};
    }
}
export const blindControl = Router();

function createBlind(pins: PerPosition<number>): Blind {
    return Gpio.accessible ? new GpioBlind(pins) : new NopBlind();
}

const rooms: {[k: string] : Blind} = {
    bedroom: createBlind({
        up: 24,
        down: 22,
        mid: 26
    }),
};

blindControl.get('/blinds/:room', (req, res) => {
    const room = req.params.room.toLowerCase();
    if (typeof rooms[room] === 'undefined') {
        res.json({error: `unknown room ${room}`});
        return;
    }
    res.json(rooms[room].getState());
});

blindControl.post('/blinds/:room', (req, res) => {
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
