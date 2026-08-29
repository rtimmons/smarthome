import {expect} from 'chai';

const {
    operationFromResponse,
    SONOS_ZONE_MUTATION_TIMEOUT_MS,
    SonosOperationGate,
    terminalOperationFromStatus,
    topologyMutationAllowed,
}: any = require('./sonos-operation-state');

describe('SonosOperationGate', () => {
    it('allows topology writes only from live observations', () => {
        expect(topologyMutationAllowed('live')).to.equal(true);
        expect(topologyMutationAllowed('stale')).to.equal(false);
        expect(topologyMutationAllowed('unknown')).to.equal(false);
    });

    it('freezes the Dashboard pending deadline at 50 seconds', () => {
        expect(SONOS_ZONE_MUTATION_TIMEOUT_MS).to.equal(50_000);
    });

    it('recognizes every terminal operation result', () => {
        [
            'completed',
            'partial',
            'partially_completed',
            'partial_success',
            'failed',
            'timed_out',
            'cancelled',
            'superseded',
        ].forEach(status => {
            const operation = {id: 'operation-' + status, status};
            expect(
                terminalOperationFromStatus({
                    activeIntent: status === 'completed' ? null : operation,
                    recentIntent: status === 'completed' ? operation : null,
                })
            ).to.equal(operation);
        });
        expect(
            terminalOperationFromStatus({
                activeIntent: {id: 'running-operation', status: 'running'},
                recentIntent: null,
            })
        ).to.equal(null);
    });

    it('extracts both compatibility intent and operation responses', () => {
        expect(operationFromResponse({intent: {id: 'intent-1'}}).id).to.equal(
            'intent-1'
        );
        expect(
            operationFromResponse({operation: {id: 'operation-1'}}).id
        ).to.equal('operation-1');
    });

    it('ignores a late response from a superseded request', () => {
        const gate = new SonosOperationGate();
        const first = gate.begin();
        const second = gate.begin();

        expect(
            gate.acceptResponse(first, {operation: {id: 'old-operation'}})
        ).to.equal(null);
        expect(
            gate.acceptResponse(second, {operation: {id: 'new-operation'}}).id
        ).to.equal('new-operation');
    });

    it('ignores status for an older operation after a newer one starts', () => {
        const gate = new SonosOperationGate();
        const first = gate.begin();
        gate.acceptResponse(first, {intent: {id: 'old-operation'}});
        const second = gate.begin();

        expect(
            gate.filterStatus({
                activeIntent: {id: 'old-operation', status: 'running'},
                recentIntent: null,
            })
        ).to.equal(null);

        gate.acceptResponse(second, {operation: {id: 'new-operation'}});
        expect(
            gate.filterStatus({
                activeIntent: {id: 'old-operation', status: 'running'},
                recentIntent: null,
            })
        ).to.equal(null);
        expect(
            gate.filterStatus({
                activeIntent: {id: 'new-operation', status: 'running'},
                recentIntent: {id: 'old-operation', status: 'superseded'},
            }).activeIntent.id
        ).to.equal('new-operation');
    });

    it('adopts an in-flight operation after a page reload', () => {
        const gate = new SonosOperationGate();
        const status = {
            activeIntent: {id: 'existing-operation', status: 'running'},
            recentIntent: null,
        };

        expect(gate.filterStatus(status)).to.equal(status);
        expect(gate.operationId).to.equal('existing-operation');
    });
});
