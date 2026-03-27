class GridView {
    constructor(args) {
        this.$element = args.container;
        var config = args.config;
        this.config = config;

        this.pubsub = args.pubsub;
        this.cells = [];
        this.cols = config.cols;
        this.rows = config.rows;
        this.zoneCells = {};
        this.cellsByKey = {};
    }

    allCells() {
        return this.cells;
    }

    onResize(width, height) {
        var square = Math.min(
            Math.ceil(width / this.cols),
            Math.ceil(height / this.rows)
        );
        this.square = square;
        $('.cell').each(function() {
            var t = $(this);
            var width = (t.attr('colspan') || 1) * square + 'px';
            t.css({
                height: (t.attr('rowspan') || 1) * square + 0 + 'px',
                width: width,
                maxWidth: width,
                fontSize: (square * 2) / 3 + 'px',
                lineHeight: square + 'px',
            });
        });

        this.$element.width((square + 2) * this.cols);
    }

    // TODO: each cell is a listener
    updateZones(onoff) {
        // could optimize in the future
        this.allCells().forEach(c => {
            var room = c.togglesRoom();
            if (!room) {
                return;
            }
            c.setActive(onoff.on.indexOf(c.togglesRoom()) >= 0);
        });
    }

    _createElement(size) {
        var cell = this.$element.find('#cell-' + size.y + '-' + size.x);

        if (size.w == 0 || size.h == 0) {
            cell.remove();
        } else {
            cell.attr('colspan', size.w);
        }
        return cell;
    }

    _cellKey(x, y) {
        return y + ':' + x;
    }

    _findRoomCell(roomName) {
        for (var i = 0; i < this.cells.length; i++) {
            if (this.cells[i].isActiveForRoom(roomName)) {
                return this.cells[i];
            }
        }
        return null;
    }

    _findToggleCell(roomName) {
        for (var i = 0; i < this.cells.length; i++) {
            if (this.cells[i].togglesRoom() === roomName) {
                return this.cells[i];
            }
        }
        return null;
    }

    updateIntent(status) {
        var activeIntent = status && status.activeIntent;
        var pendingStrength = 0;

        this.allCells().forEach(function(cell) {
            cell.clearIntentClasses();
        });

        if (!activeIntent) {
            return;
        }

        var roomCell = this._findRoomCell(activeIntent.targetRoom);
        if (roomCell) {
            roomCell.setIntentClass('intent-target', true);
        }

        if (!Array.isArray(activeIntent.missingRooms)) {
            return;
        }

        pendingStrength = Math.max(
            0.18,
            0.82 - ((activeIntent.attemptCount || 0) * 0.08)
        );
        activeIntent.missingRooms.forEach(roomName => {
            var toggleCell = this._findToggleCell(roomName);
            if (!toggleCell) {
                return;
            }
            toggleCell.setIntentClass('intent-pending', true);
            toggleCell.setIntentPendingStrength(pendingStrength);
        });
    }

    updateCells(cells) {
        var grid = this;
        cells.forEach(function(config) {
            var key = grid._cellKey(config.x, config.y);
            var cell = grid.cellsByKey[key];
            if (!cell) {
                throw new Error(
                    'Unknown cell at (' + config.x + ',' + config.y + ').'
                );
            }
            cell.updateConfig(config);
        });
    }

    init($win, app) {
        this.app = app;
        var grid = this;

        for (var row = 0; row < this.rows; row++) {
            var tr = $('<tr>');
            for (var col = 0; col < this.cols; col++) {
                var cell = $('<td class="cell">');
                // cell.addClass('row-'+row);
                // cell.addClass('col-'+col);
                cell.attr('id', 'cell-' + row + '-' + col);
                var span = $('<div class="content"></div>');
                cell.append(span);
                tr.append(cell);
            }
            this.$element.append(tr);
        }

        this.config.cells.forEach(b => {
            var cell = new CellView({
                grid: grid,
                app: this.app,
                pubsub: this.pubsub,
                $element: this._createElement(b),
                config: b,
            });
            this.cells.push(cell);
            this.cellsByKey[this._cellKey(b.x, b.y)] = cell;
        });

        $win.resize(function() {
            grid.onResize($win.width(), $win.height());
        }).resize();
    }
}
