(function(root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.ConfigResolver = factory();
    }
})(this, function() {
    const cellKey = function(x, y) {
        return y + ':' + x;
    };

    const normalizeDim = function(value) {
        return value === undefined || value === null ? 1 : value;
    };

    const cellDims = function(cell) {
        return {
            w: normalizeDim(cell.w),
            h: normalizeDim(cell.h),
        };
    };

    const isNonStandardCell = function(cell) {
        const dims = cellDims(cell);
        return dims.w !== 1 || dims.h !== 1;
    };

    const createBaseIndex = function(config) {
        if (!config) {
            throw new Error('Config is required.');
        }
        if (!config.cells) {
            throw new Error('Config.cells is required.');
        }

        var rows = config.rows;
        var cols = config.cols;
        if (rows === undefined || cols === undefined) {
            throw new Error('Config.rows and config.cols are required.');
        }

        var cellsByKey = {};
        var indicesByKey = {};
        config.cells.forEach(function(cell, index) {
            if (cell.x === undefined || cell.y === undefined) {
                throw new Error('Cell missing x/y coordinates.');
            }
            if (cell.x < 0 || cell.x >= cols || cell.y < 0 || cell.y >= rows) {
                throw new Error(
                    'Cell at (' +
                        cell.x +
                        ',' +
                        cell.y +
                        ') is outside the grid.'
                );
            }
            var key = cellKey(cell.x, cell.y);
            if (Object.prototype.hasOwnProperty.call(cellsByKey, key)) {
                throw new Error(
                    'Duplicate base cell at (' +
                        cell.x +
                        ',' +
                        cell.y +
                        ').'
                );
            }
            cellsByKey[key] = cell;
            indicesByKey[key] = index;
        });

        for (var y = 0; y < rows; y++) {
            for (var x = 0; x < cols; x++) {
                var key = cellKey(x, y);
                if (!Object.prototype.hasOwnProperty.call(cellsByKey, key)) {
                    throw new Error(
                        'Base config missing cell at (' + x + ',' + y + ').'
                    );
                }
            }
        }

        return {
            rows: rows,
            cols: cols,
            cellsByKey: cellsByKey,
            indicesByKey: indicesByKey,
        };
    };

    const validateOverrideCell = function(roomName, overrideCell, baseCell) {
        var coords = '(' + overrideCell.x + ',' + overrideCell.y + ')';
        if (!baseCell) {
            throw new Error(
                'Room override for "' +
                    roomName +
                    '" references unknown cell at ' +
                    coords +
                    '. Overrides must target existing base cells.'
            );
        }
        if (isNonStandardCell(overrideCell)) {
            throw new Error(
                'Room override for "' +
                    roomName +
                    '" defines a non-1x1 cell at ' +
                    coords +
                    '. Wide cells cannot be overridden.'
            );
        }
        if (isNonStandardCell(baseCell)) {
            throw new Error(
                'Room override for "' +
                    roomName +
                    '" targets a non-1x1 cell at ' +
                    coords +
                    '. Wide cells cannot be overridden.'
            );
        }
    };

    const validateConfig = function(config) {
        var baseIndex = createBaseIndex(config);
        var roomOverrides = config.roomOverrides || {};
        Object.keys(roomOverrides).forEach(function(roomName) {
            var override = roomOverrides[roomName];
            if (!override) {
                return;
            }
            var overrideCells = override.cells || [];
            var seen = {};
            overrideCells.forEach(function(cell) {
                var key = cellKey(cell.x, cell.y);
                if (Object.prototype.hasOwnProperty.call(seen, key)) {
                    throw new Error(
                        'Room override for "' +
                            roomName +
                            '" repeats cell at (' +
                            cell.x +
                            ',' +
                            cell.y +
                            ').'
                    );
                }
                seen[key] = true;
                validateOverrideCell(
                    roomName,
                    cell,
                    baseIndex.cellsByKey[key]
                );
            });
        });
    };

    const mergeCells = function(baseCells, overrideCells, baseIndex) {
        var merged = baseCells.map(function(cell) {
            return Object.assign({}, cell);
        });
        overrideCells.forEach(function(overrideCell) {
            var key = cellKey(overrideCell.x, overrideCell.y);
            var index = baseIndex.indicesByKey[key];
            if (index === undefined) {
                throw new Error(
                    'Override references unknown cell at (' +
                        overrideCell.x +
                        ',' +
                        overrideCell.y +
                        ').'
                );
            }
            merged[index] = Object.assign({}, merged[index], overrideCell);
        });
        return merged;
    };

    const resolveRoomConfig = function(baseConfig, roomName) {
        var override =
            baseConfig.roomOverrides && baseConfig.roomOverrides[roomName];
        if (!override || !override.cells || !override.cells.length) {
            return baseConfig;
        }

        var baseIndex = createBaseIndex(baseConfig);
        var resolved = Object.assign({}, baseConfig);
        resolved.cells = mergeCells(baseConfig.cells, override.cells, baseIndex);
        resolved.roomOverrides = baseConfig.roomOverrides;
        return resolved;
    };

    return {
        resolveRoomConfig: resolveRoomConfig,
        validateConfig: validateConfig,
    };
});
