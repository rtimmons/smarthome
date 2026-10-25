class PrinterController {
    constructor(args) {
        this.app = args.app;
        this.port = args.port || 8099;
    }

    preset(slug) {
        if (!slug) {
            return;
        }
        const url = this._buildPresetUrl(slug);
        this.app.window.location.assign(url);
    }

    _buildPresetUrl(slug) {
        // Uses the printer add-on preset URL scheme to trigger countdown prints and auto-return.
        const location = this.app.window.location;
        if (location.hostname === 'grid-dashboard.home.rytim.com') {
            return 'https://printer.home.rytim.com/p/' + encodeURIComponent(slug) + '?print=true';
        }
        const protocol = location.protocol || 'http:';
        const hostname = location.hostname;
        return (
            protocol +
            '//' +
            hostname +
            ':' +
            this.port +
            '/p/' +
            encodeURIComponent(slug) +
            '?print=true'
        );
    }
}
