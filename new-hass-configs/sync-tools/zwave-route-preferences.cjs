const fs = require('node:fs');
const path = require('node:path');

function validatePlan(plan) {
  const validId = id => Number.isInteger(id) && id > 1 && id <= 232;
  if (!Number.isInteger(plan.homeId) || plan.homeId <= 0 || plan.homeId > 0xffffffff
      || !Array.isArray(plan.routes) || !plan.routes.length) throw Error('Invalid route plan');
  const ids = new Set();
  for (const route of plan.routes) {
    if (!validId(route.nodeId) || ids.has(route.nodeId) || ![1, 2, 3].includes(route.routeSpeed)
        || !Array.isArray(route.repeaters) || route.repeaters.length > 4
        || new Set(route.repeaters).size !== route.repeaters.length
        || route.repeaters.some(id => !validId(id) || id === route.nodeId)) throw Error('Invalid or duplicate route');
    ids.add(route.nodeId);
  }
}

// Self-contained: this function executes in the authenticated app's driver context.
async function manageRoutes(driver, plan, action) {
  if (driver.controller.homeId !== plan.homeId) throw Error('Wrong Z-Wave network; no changes made');
  for (const route of plan.routes) {
    for (const id of [route.nodeId, ...route.repeaters]) {
      if (!driver.controller.nodes.has(id)) throw Error(`Node ${id} missing; no changes made`);
    }
  }
  const results = [];
  for (const route of plan.routes) {
    const before = await driver.controller.getPriorityRoute(route.nodeId);
    const matches = before?.routeKind === 16 && before.routeSpeed === route.routeSpeed
      && JSON.stringify(before.repeaters) === JSON.stringify(route.repeaters);
    let changed = false;
    if (action === 'apply' && !matches) {
      if (!await driver.controller.setPriorityRoute(route.nodeId, route.repeaters, route.routeSpeed)) {
        throw Error(`Route assignment failed for node ${route.nodeId}; inspect saved backup before retrying`);
      }
      changed = true;
    } else if (action === 'remove' && matches) {
      if (!await driver.controller.removePriorityRoute(route.nodeId)) throw Error(`Removal failed for node ${route.nodeId}`);
      changed = true;
    }
    // Removal never overwrites a different preference set by someone else.
    results.push({ nodeId: route.nodeId, before, matches, changed,
      after: changed ? await driver.controller.getPriorityRoute(route.nodeId) : before });
  }
  return results;
}

async function main() {
  const action = process.argv[2] || 'check';
  if (!['check', 'apply', 'remove'].includes(action)) throw Error('Use check, apply, or remove');
  const plan = JSON.parse(fs.readFileSync(path.join(__dirname, '../zwave-route-preferences.json'), 'utf8'));
  validatePlan(plan);
  const call = require('./zwave-ui-api.cjs');
  const run = mode => call({ api: 'driverFunction', args: [
    `return (${manageRoutes.toString()})(driver, ${JSON.stringify(plan)}, ${JSON.stringify(mode)});`,
  ] });
  const before = await run('check');
  if (action !== 'check') {
    const directory = path.join(__dirname, '../backups/zwave-js');
    fs.mkdirSync(directory, { recursive: true });
    const backup = path.join(directory, `routes-${Date.now()}.json`);
    fs.writeFileSync(backup, JSON.stringify({ homeId: plan.homeId, before }, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
    console.log(`Saved route backup: ${backup}`);
  }
  const results = action === 'check' ? before : await run(action);
  for (const result of results) console.log(`Node ${result.nodeId}: ${JSON.stringify(result.after || null)}`);
  if (action !== 'remove') {
    const checked = action === 'check' ? results : await run('check');
    if (checked.some(result => !result.matches)) throw Error('One or more route preferences do not match');
  }
}

module.exports = { validatePlan, manageRoutes };
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
