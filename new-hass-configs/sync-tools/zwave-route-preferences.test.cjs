const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validatePlan, manageRoutes } = require('./zwave-route-preferences.cjs');
const plan = { homeId: 123, routes: [{ nodeId: 7, repeaters: [], routeSpeed: 2 }] };

test('rejects malformed, looping, and duplicate route plans', () => {
  validatePlan(plan);
  for (const routes of [[], [plan.routes[0], plan.routes[0]], [{ nodeId: 7, repeaters: [7], routeSpeed: 2 }], [{ nodeId: 1, repeaters: [], routeSpeed: 2 }]]) {
    assert.throws(() => validatePlan({ ...plan, routes }));
  }
});

function fixture(route) {
  const calls = [];
  const controller = {
    homeId: 123, nodes: new Map([[7, {}]]),
    async getPriorityRoute() { return route; },
    async setPriorityRoute(...args) { calls.push(['set', ...args]); route = { routeKind: 16, repeaters: args[1], routeSpeed: args[2] }; return true; },
    async removePriorityRoute(id) { calls.push(['remove', id]); route = undefined; return true; },
  };
  return { driver: { controller }, calls };
}

test('network and complete node list are checked before the first mutation', async () => {
  const f = fixture();
  await assert.rejects(manageRoutes(f.driver, { ...plan, homeId: 456 }, 'apply'), /Wrong/);
  await assert.rejects(manageRoutes(f.driver, { ...plan, routes: [...plan.routes, { nodeId: 8, repeaters: [], routeSpeed: 2 }] }, 'apply'), /missing/);
  assert.deepEqual(f.calls, []);
});

test('check is read-only and applying an existing preference is idempotent', async () => {
  const f = fixture();
  await manageRoutes(f.driver, plan, 'check');
  assert.deepEqual(f.calls, []);
  await manageRoutes(f.driver, plan, 'apply');
  await manageRoutes(f.driver, plan, 'apply');
  assert.deepEqual(f.calls, [['set', 7, [], 2]]);
});

test('removal preserves a different application preference', async () => {
  const f = fixture({ routeKind: 16, repeaters: [], routeSpeed: 1 });
  await manageRoutes(f.driver, plan, 'remove');
  assert.deepEqual(f.calls, []);
  await manageRoutes(f.driver, plan, 'apply');
  await manageRoutes(f.driver, plan, 'remove');
  assert.deepEqual(f.calls, [['set', 7, [], 2], ['remove', 7]]);
});
