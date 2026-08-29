function topologyMutationAllowed(freshness) {
    return freshness === 'live';
}

// The backend operation deadline is 45 seconds. Keep the panel pending for a
// small, fixed delivery margin so a final correlated status poll can release
// it instead of re-enabling the control while the backend is still active.
var SONOS_ZONE_MUTATION_TIMEOUT_MS = 50 * 1000;

var TERMINAL_OPERATION_STATUSES = {
    completed: true,
    partial: true,
    partially_completed: true,
    partial_success: true,
    failed: true,
    timed_out: true,
    cancelled: true,
    superseded: true,
};

function operationFromResponse(response) {
    if (!response || typeof response !== 'object') {
        return null;
    }

    return response.operation || response.intent ||
        (response.id ? response : null);
}

function operationCandidates(status) {
    if (!status || typeof status !== 'object') {
        return [];
    }

    return [status.activeIntent, status.recentIntent].filter(function(intent) {
        return intent && intent.id;
    });
}

function terminalOperationFromStatus(status) {
    var candidates = operationCandidates(status);
    for (var i = 0; i < candidates.length; i++) {
        if (TERMINAL_OPERATION_STATUSES[candidates[i].status]) {
            return candidates[i];
        }
    }
    return null;
}

class SonosOperationGate {
    constructor() {
        this.generation = 0;
        this.awaitingResponse = false;
        this.operationId = null;
        this.ignoredOperationIds = {};
    }

    begin() {
        if (this.operationId) {
            this.ignoredOperationIds[this.operationId] = true;
        }
        this.generation += 1;
        this.awaitingResponse = true;
        this.operationId = null;
        return this.generation;
    }

    acceptsGeneration(generation) {
        return generation === this.generation;
    }

    acceptResponse(generation, response) {
        if (!this.acceptsGeneration(generation)) {
            return null;
        }

        this.awaitingResponse = false;
        var operation = operationFromResponse(response);
        if (operation && operation.id) {
            this.operationId = operation.id;
        }
        return operation;
    }

    fail(generation) {
        if (!this.acceptsGeneration(generation)) {
            return false;
        }
        this.awaitingResponse = false;
        return true;
    }

    filterStatus(status) {
        if (this.awaitingResponse) {
            return null;
        }

        var candidates = operationCandidates(status);
        if (this.operationId) {
            if (candidates.length === 0) {
                this.operationId = null;
                return status || {};
            }
            var matching = candidates.filter(function(intent) {
                return intent.id === this.operationId;
            }, this)[0];
            if (!matching) {
                return null;
            }
            return {
                activeIntent:
                    status.activeIntent && status.activeIntent.id === this.operationId
                        ? status.activeIntent
                        : null,
                recentIntent:
                    status.recentIntent && status.recentIntent.id === this.operationId
                        ? status.recentIntent
                        : null,
                serverTime: status.serverTime,
            };
        }

        var candidate = candidates.filter(function(intent) {
            return !this.ignoredOperationIds[intent.id];
        }, this)[0];
        if (!candidate) {
            return candidates.length === 0 ? status || {} : null;
        }

        this.operationId = candidate.id;
        return status;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        operationFromResponse: operationFromResponse,
        SONOS_ZONE_MUTATION_TIMEOUT_MS: SONOS_ZONE_MUTATION_TIMEOUT_MS,
        SonosOperationGate: SonosOperationGate,
        terminalOperationFromStatus: terminalOperationFromStatus,
        topologyMutationAllowed: topologyMutationAllowed,
    };
}
