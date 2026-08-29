import {strict as assert} from 'assert';

import {SonosBackendError} from './sonos-contract';
import {deferred, nextTurn} from './home-assistant-test-fixtures';
import {SonosOperationQueue} from './sonos-operation-queue';
import type {SonosOperationLogRecord} from './sonos-operation-queue';
import type {SonosRoomName} from './sonos-room-map';

const run = async (): Promise<void> => {
  let now = 1;
  let id = 0;
  const queue = new SonosOperationQueue({
    now: () => now++,
    id: () => `operation-${++id}`,
  });
  const firstGate = deferred<void>();
  const calls: string[] = [];
  const first = queue.enqueue({
    kind: 'join_all',
    key: 'same-request',
    requestedRooms: ['Kitchen'],
    run: async () => {
      calls.push('first');
      await firstGate.promise;
    },
  });
  const duplicate = queue.enqueue({
    kind: 'join_all',
    key: 'same-request',
    requestedRooms: ['Kitchen'],
    run: async () => { calls.push('duplicate'); },
  });
  assert.equal(duplicate.coalesced, true);
  assert.equal(duplicate.operation.id, first.operation.id);

  const discarded = queue.enqueue({
    kind: 'leave',
    key: 'leave:Office',
    requestedRooms: ['Office'],
    run: async () => { calls.push('discarded'); },
  });
  const newest = queue.enqueue({
    kind: 'leave',
    key: 'leave:Kitchen',
    requestedRooms: ['Kitchen'],
    run: async () => { calls.push('newest'); },
  });
  assert.equal((await discarded.finished).status, 'superseded');
  firstGate.resolve();
  assert.equal((await first.finished).status, 'superseded');
  assert.equal((await newest.finished).status, 'completed');
  assert.deepEqual(calls, ['first', 'newest'],
    'duplicates and an older queued request never execute');

  const timeoutQueue = new SonosOperationQueue({id: () => 'timeout'});
  const timedOut = timeoutQueue.enqueue({
    kind: 'join',
    key: 'timeout',
    requestedRooms: ['Kitchen'],
    run: async () => {
      throw new SonosBackendError('operation_timeout', 'deadline', 504, true);
    },
  });
  await nextTurn();
  const result = await timedOut.finished;
  assert.equal(result.status, 'timed_out');
  assert.equal(result.error, 'deadline');

  {
    let clock = 100;
    const records: SonosOperationLogRecord[] = [];
    const loggedQueue = new SonosOperationQueue({
      id: () => 'logged-operation',
      now: () => clock,
      logger: record => records.push(record),
    });
    const logged = loggedQueue.enqueue({
      kind: 'join',
      key: 'logged',
      requestedRooms: ['Kitchen'],
      run: async context => {
        context.recordServiceCall();
        context.recordServiceCall();
        clock = 125;
      },
    });
    const loggedResult = await logged.finished;
    assert.equal(loggedResult.serviceCallCount, 2);
    assert.deepEqual(records, [{
      event: 'sonos_operation_terminal',
      operationId: 'logged-operation',
      kind: 'join',
      backend: 'home_assistant',
      status: 'completed',
      serviceCallCount: 2,
      startedAt: 100,
      finishedAt: 125,
      durationMs: 25,
      unavailableRooms: [],
    }]);
  }

  {
    const failureQueue = new SonosOperationQueue({id: () => 'preset-failure'});
    const failure = Object.assign(
      new SonosBackendError('preset_step_failed', 'preset step failed', 502),
      {
        failedStep: 'select_source:Bedroom',
        observedTopology: [{
          coordinator: 'Bedroom' as const,
          members: ['Bedroom', 'Kitchen'] as SonosRoomName[],
        }],
      }
    );
    const failed = failureQueue.enqueue({
      kind: 'preset',
      key: 'preset-failure',
      requestedRooms: ['Bedroom'],
      run: async () => { throw failure; },
    });
    const failedResult = await failed.finished;
    assert.equal(failedResult.failedStep, 'select_source:Bedroom');
    assert.deepEqual(failedResult.observedTopology, [{
      coordinator: 'Bedroom',
      members: ['Bedroom', 'Kitchen'],
    }]);
    failure.observedTopology[0].members.push('Office');
    assert.deepEqual(failedResult.observedTopology?.[0].members, ['Bedroom', 'Kitchen'],
      'returned operation details are isolated from later mutation');
  }

  {
    let clock = 10_000;
    const retentionQueue = new SonosOperationQueue({
      now: () => clock,
      id: () => 'retained',
      terminalRetentionMs: 5 * 60 * 1000,
    });
    const retained = retentionQueue.enqueue({
      kind: 'join_all',
      key: 'retention',
      targetRoom: 'Bedroom',
      requestedRooms: ['Bedroom', 'Kitchen'],
      run: async () => undefined,
    });
    const completed = await retained.finished;
    assert.equal(completed.targetRoom, 'Bedroom');
    const finishedAt = completed.finishedAt as number;
    clock = finishedAt + 5 * 60 * 1000 - 1;
    assert.equal(retentionQueue.getOperation('retained')?.status, 'completed');
    clock = finishedAt + 5 * 60 * 1000;
    assert.equal(retentionQueue.getOperation('retained'), undefined,
      'terminal history expires at the exact five-minute boundary');
  }

  {
    const gate = deferred<void>();
    const cancellationQueue = new SonosOperationQueue({id: () => 'cancel-me'});
    const pending = cancellationQueue.enqueue({
      kind: 'join',
      key: 'cancel',
      requestedRooms: ['Kitchen'],
      run: async context => {
        await gate.promise;
        assert.equal(context.isCancelled(), true);
      },
    });
    assert.equal(
      cancellationQueue.cancelOperation('cancel-me', 'shutdown')?.status,
      'cancelled'
    );
    gate.resolve();
    const cancelled = await pending.finished;
    assert.equal(cancelled.status, 'cancelled',
      'a late in-flight completion cannot overwrite cancellation');
    assert.equal(cancelled.error, 'shutdown');
  }

  {
    let clock = 0;
    const gate = deferred<void>();
    const timers: Array<{
      callback: () => void;
      at: number;
      cleared: boolean;
    }> = [];
    const boundaryQueue = new SonosOperationQueue({
      now: () => clock,
      id: () => 'deadline-boundary',
      operationDeadlineMs: 45_000,
      setTimeout: ((callback: () => void, delay = 0) => {
        const timer = {callback, at: clock + delay, cleared: false};
        timers.push(timer);
        return timer as any;
      }) as typeof setTimeout,
      clearTimeout: ((timer: any) => {
        timer.cleared = true;
      }) as typeof clearTimeout,
    });
    const pending = boundaryQueue.enqueue({
      kind: 'join',
      key: 'deadline-boundary',
      requestedRooms: ['Kitchen'],
      run: async () => gate.promise,
    });
    const advanceTo = (target: number): void => {
      clock = target;
      for (const timer of timers.filter(candidate =>
        !candidate.cleared && candidate.at <= target
      )) {
        timer.cleared = true;
        timer.callback();
      }
    };

    advanceTo(44_999);
    assert.equal(boundaryQueue.getOperation('deadline-boundary')?.status, 'running',
      'an operation remains active immediately before its 45-second deadline');
    advanceTo(45_000);
    assert.equal((await pending.finished).status, 'timed_out',
      'an operation times out at the exact 45-second deadline');
    gate.resolve();
    await nextTurn();
    assert.equal(boundaryQueue.getOperation('deadline-boundary')?.status, 'timed_out',
      'late completion cannot rewrite the deadline result');
  }

  {
    let clock = 0;
    let deadlineId = 0;
    const firstGate = deferred<void>();
    let secondRuns = 0;
    const deadlines = new SonosOperationQueue({
      now: () => clock,
      id: () => `deadline-${++deadlineId}`,
      operationDeadlineMs: 45_000,
    });
    const first = deadlines.enqueue({
      kind: 'join_all',
      key: 'first-deadline',
      requestedRooms: ['Bedroom'],
      run: async () => firstGate.promise,
    });
    clock = 10_000;
    const second = deadlines.enqueue({
      kind: 'leave',
      key: 'second-deadline',
      requestedRooms: ['Kitchen'],
      run: async () => { secondRuns += 1; },
    });
    assert.equal(second.operation.deadlineAt, 55_000,
      'the deadline is frozen when the request is accepted, not when it starts');
    clock = 55_000;
    firstGate.resolve();
    assert.equal((await first.finished).status, 'superseded');
    assert.equal((await second.finished).status, 'timed_out');
    assert.equal(secondRuns, 0, 'expired queued work makes no Home Assistant call');
  }
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
