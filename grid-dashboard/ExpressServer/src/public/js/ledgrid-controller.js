class LedGridController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
    }

    start(animation, config) {
        if (!animation) {
            return;
        }
        const url = this._buildUrl(['ledgrid', 'start', animation]);
        const payload = config ? JSON.stringify(config) : '{}';
        return this.requester.request({
            url: url,
            method: 'POST',
            data: payload,
            contentType: 'application/json',
        });
    }

    stop() {
        const url = this._buildUrl(['ledgrid', 'stop']);
        return this.requester.request({
            url: url,
            method: 'POST',
        });
    }

    _buildUrl(parts) {
        const encoded = parts.map(part => encodeURIComponent(part));
        if (!this.root) {
            const basePath = window.location.pathname.replace(/\/+$/, '');
            return basePath + '/' + encoded.join('/');
        }
        return [this.root].concat(encoded).join('/');
    }
}
