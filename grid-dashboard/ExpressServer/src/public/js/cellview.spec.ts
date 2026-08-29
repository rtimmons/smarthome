import { expect } from 'chai';

const { CellView, PressDispatcher }: any = require('./cellview');

describe('CellView Sonos zone state', () => {
    it('shows unknown without changing the last active membership', () => {
        const content: string[] = [];
        const classes: Array<[string, boolean]> = [];
        const cell: any = Object.create(CellView.prototype);
        cell.active = true;
        cell.zoneUnknown = false;
        cell.config = {togglesRoom: 'Kitchen', emoji: 'speaker'};
        cell.app = {emojiWithName: (name: string) => name};
        cell.setContent = (value: string) => content.push(value);
        cell.$element = {
            toggleClass: (name: string, enabled: boolean) =>
                classes.push([name, enabled]),
        };

        cell.setZoneUnknown(true);

        expect(cell.isActive()).to.equal(true);
        expect(content).to.deep.equal(['?']);
        expect(classes).to.deep.equal([['zone-unknown', true]]);
    });
});

describe('PressDispatcher', () => {
    it('cancels a pending single press when a double press arrives', () => {
        const scheduled: Array<() => void> = [];
        const cancelled = new Set<() => void>();
        let singles = 0;
        let doubles = 0;
        const dispatcher = new PressDispatcher({
            onSingle: () => singles++,
            onDouble: () => doubles++,
            hasDouble: () => true,
            schedule: (callback: () => void) => {
                scheduled.push(callback);
                return callback;
            },
            cancel: (callback: () => void) => cancelled.add(callback),
        });

        dispatcher.single();
        dispatcher.double();
        scheduled.filter(callback => !cancelled.has(callback)).forEach(callback => callback());

        expect(singles).to.equal(0);
        expect(doubles).to.equal(1);
    });

    it('fires immediately when no double action exists', () => {
        let singles = 0;
        const dispatcher = new PressDispatcher({
            onSingle: () => singles++,
            onDouble: () => undefined,
            hasDouble: () => false,
        });

        dispatcher.single();

        expect(singles).to.equal(1);
    });

    it('uses the default timer without rebinding the timer global', async () => {
        let singles = 0;
        const dispatcher = new PressDispatcher({
            onSingle: () => singles++,
            onDouble: () => undefined,
            hasDouble: () => true,
            delay: 0,
        });

        dispatcher.single();
        await new Promise(resolve => setTimeout(resolve, 5));

        expect(singles).to.equal(1);
    });
});
