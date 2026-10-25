import {expect} from 'chai';
import {readFileSync} from 'fs';
import {createContext, runInContext} from 'vm';

describe('Printer browser links', () => {
    const build = (hostname: string, protocol: string) => {
        const context = createContext({});
        const Controller = runInContext(
            readFileSync(require.resolve('./printer-controller.js'), 'utf8') + '\nPrinterController', context
        );
        return new Controller({app: {window: {location: {hostname, protocol}}}})
            ._buildPresetUrl('fixture / label');
    };
    it('uses the protected printer entrance from the HTTPS dashboard', () => {
        expect(build('grid-dashboard.home.rytim.com', 'https:'))
            .to.equal('https://printer.home.rytim.com/p/fixture%20%2F%20label?print=true');
    });
    it('preserves direct LAN and ingress printer links', () => {
        for (const hostname of ['grid-dashboard.home.arpa', '192.168.1.163']) {
            expect(build(hostname, 'http:'))
                .to.equal('http://' + hostname + ':8099/p/fixture%20%2F%20label?print=true');
        }
    });
});
