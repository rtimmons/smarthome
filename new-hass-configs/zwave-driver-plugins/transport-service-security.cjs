// Temporary backport for Z-Wave JS 15.31.1. Upstream #8885 removed the
// Transport Service exception originally fixed by #5966. Reassembled
// application commands still go through the driver's original security check.
// Remove this plugin after verifying an upstream fix in the installed driver.
const CONTROL_COMMANDS = new Map([
  [0xc8, 'TransportServiceCCSegmentRequest'],
  [0xe8, 'TransportServiceCCSegmentComplete'],
  [0xf0, 'TransportServiceCCSegmentWait'],
]);
const PATCH = Symbol.for('smarthome.transport-service-security.15.31.1');

module.exports = class TransportServiceSecurity {
  constructor({ zwave, logger }) {
    this.zwave = zwave;
    this.logger = logger;
    this.patched = new Map();
    this.onEvent = (source, event) => {
      if (source === 'driver' && event === 'driver ready') this.install();
    };
    zwave.on('event', this.onEvent);
    this.install();
  }

  install() {
    const driver = this.zwave.driver;
    if (!driver || driver[PATCH]) return;
    const version = this.zwave.getInfo().zwaveVersion;
    if (version !== '15.31.1') {
      this.logger.error(`Transport Service hotfix inactive: unvalidated driver ${version}; check whether upstream has fixed #8885 before updating this plugin.`);
      return;
    }
    const original = driver.isSecurityLevelTooLow;
    if (typeof original !== 'function') {
      this.logger.error('Transport Service hotfix inactive: driver security hook unavailable.');
      return;
    }
    const plugin = this;
    function checkSecurity(cc) {
      // These three protocol controls contain no application payload and are
      // outside S2 by design. Never bypass checks for fragments, reassembled
      // payloads, other command classes, or a node unknown to the controller.
      if (cc.ccId === 0x55
          && CONTROL_COMMANDS.has(cc.ccCommand)
          && CONTROL_COMMANDS.get(cc.ccCommand) === cc.constructor.name
          && Number.isInteger(cc.nodeId)
          && this.controller.nodes.has(cc.nodeId)) {
        this.driverLog.print(`Transport Service hotfix accepted ${cc.constructor.name} from node ${cc.nodeId}`, 'debug');
        return false;
      }
      return original.call(this, cc);
    }
    driver.isSecurityLevelTooLow = checkSecurity;
    driver[PATCH] = true;
    plugin.patched.set(driver, { original, replacement: checkSecurity });
    driver.driverLog.print('Smarthome Transport Service security hotfix active (15.31.1; fragment controls only)', 'warn');
    this.logger.info('Transport Service security hotfix active for Z-Wave JS 15.31.1');
  }

  async destroy() {
    this.zwave.off('event', this.onEvent);
    for (const [driver, { original, replacement }] of this.patched) {
      if (driver.isSecurityLevelTooLow === replacement) {
        driver.isSecurityLevelTooLow = original;
        delete driver[PATCH];
      }
    }
    this.patched.clear();
  }
};
