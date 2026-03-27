import { expect } from 'chai';

const listeners: any = require('./listeners');

describe('listeners banner formatting', () => {
    it('formats standard tracks with em dash separator', () => {
        const banner = listeners.formatBannerText({
            title: 'Teardrop',
            artist: 'Massive Attack',
            stationName: '',
        });

        expect(banner).to.equal('Teardrop — Massive Attack');
    });

    it('parses SiriusXM metadata embedded in the title', () => {
        const banner = listeners.formatBannerText({
            title:
                "TYPE=SNG|TITLE Immortal (Steve Aoki Remix)|ARTIST 2LOT|ALBUM HiROQUEST 3: Paragon Remixed — CH 735 - Steve Aoki's Remix Radio",
            artist: '',
            stationName: "CH 735 - Steve Aoki's Remix Radio",
        });

        expect(banner).to.equal('Immortal (Steve Aoki Remix) - 2LOT');
    });

    it('falls back to the station name when artist is unavailable', () => {
        const banner = listeners.formatBannerText({
            title: 'Morning Edition',
            artist: '',
            stationName: 'NPR',
        });

        expect(banner).to.equal('Morning Edition — NPR');
    });
});
