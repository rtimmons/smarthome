/**
 * We use the i2c module to interact with blinds controllers, but i2c has native bindings that
 * only work on linux. For local development we don't care about actually interacting with the blinds
 * controller, so just give a dumb mock impl.
 */

const nop = (...args: any[]) => {};

let actual = {
    openSync: (...args: any[]) => actual,
    writeByteSync: nop,
    closeSync: nop,
};

try {
    actual = require('i2c-bus');
} catch(e) {
    console.log(`Using nop i2c implementation.`)
}

export const i2c = actual;

