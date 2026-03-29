(function() {
    var EMPTY_TOKEN = '..';
    var STATUS_TOKEN = 'ST';
    var GRID_CELL_SIZE = 80;
    var POINTER_DRAG_THRESHOLD = 8;

    var TOKEN_LIBRARY = {
        '..': { emoji: '', alias: 'Empty cell', press: '', activeWhen: '' },
        BA: { emoji: '🛁', alias: 'Bathroom room', press: 'ChangeRoom:Bathroom', activeWhen: '' },
        KI: { emoji: '👘', alias: 'Closet room', press: 'ChangeRoom:Closet', activeWhen: '' },
        BE: { emoji: '🛏', alias: 'Bedroom room', press: 'ChangeRoom:Bedroom', activeWhen: '' },
        TE: { emoji: '⛺️', alias: 'Move room', press: 'ChangeRoom:Move', activeWhen: '' },
        RI: { emoji: '🍙', alias: 'Kitchen room', press: 'ChangeRoom:Kitchen', activeWhen: '' },
        TV: { emoji: '📺', alias: 'Living Room room', press: 'ChangeRoom:Living Room', activeWhen: '' },
        GU: { emoji: '👨‍👨‍👦', alias: 'Guest Bathroom room', press: 'ChangeRoom:Guest Bathroom', activeWhen: '' },
        BR: { emoji: '💼', alias: 'Office room', press: 'ChangeRoom:Office', activeWhen: '' },
        S1: { emoji: '🔈', alias: 'Bathroom speaker', press: 'Music.ToggleRoom:Bathroom', activeWhen: 'in_zone:Bathroom' },
        S2: { emoji: '🔈', alias: 'Closet speaker', press: 'Music.ToggleRoom:Closet', activeWhen: 'in_zone:Closet' },
        S3: { emoji: '🔈', alias: 'Bedroom speaker', press: 'Music.ToggleRoom:Bedroom', activeWhen: 'in_zone:Bedroom' },
        S4: { emoji: '🔈', alias: 'Move speaker', press: 'Music.ToggleRoom:Move', activeWhen: 'in_zone:Move' },
        S5: { emoji: '🔈', alias: 'Kitchen speaker', press: 'Music.ToggleRoom:Kitchen', activeWhen: 'in_zone:Kitchen' },
        S6: { emoji: '🔈', alias: 'Living Room speaker', press: 'Music.ToggleRoom:Living Room', activeWhen: 'in_zone:Living Room' },
        S7: { emoji: '🔈', alias: 'Guest Bathroom speaker', press: 'Music.ToggleRoom:Guest Bathroom', activeWhen: 'in_zone:Guest Bathroom' },
        S8: { emoji: '🔈', alias: 'Office speaker', press: 'Music.ToggleRoom:Office', activeWhen: 'in_zone:Office' },
        BU: { emoji: '⬆', alias: 'Blinds roller up', press: 'Blinds.Move:Roller,Up', activeWhen: '' },
        BD: { emoji: '⬇', alias: 'Blinds roller down', press: 'Blinds.Move:Roller,Down', activeWhen: '' },
        OU: { emoji: '⏫', alias: 'Blinds blackout up', press: 'Blinds.Move:Blackout,Up', activeWhen: '' },
        OD: { emoji: '⏬', alias: 'Blinds blackout down', press: 'Blinds.Move:Blackout,Down', activeWhen: '' },
        LH: { emoji: '🌕', alias: 'Lights high', press: 'Lights.Scene:$room,High', activeWhen: '' },
        LM: { emoji: '🌘', alias: 'Lights medium', press: 'Lights.Scene:$room,Medium', activeWhen: '' },
        LO: { emoji: '🌑', alias: 'Lights off', press: 'Lights.Scene:$room,Off', activeWhen: '' },
        VU: { emoji: '🔼', alias: 'Volume up', press: 'Music.VolumeUp', activeWhen: '' },
        VM: { emoji: '🖖', alias: 'Volume same', press: 'Music.VolumeSame', activeWhen: '' },
        VD: { emoji: '🔽', alias: 'Volume down', press: 'Music.VolumeDown', activeWhen: '' },
        FI: { emoji: '🎬', alias: 'TV preset', press: 'Music.Preset:$room-tv', activeWhen: '' },
        P1: { emoji: '🪕', alias: 'Carbon Leaf preset', press: 'Music.Favorite:Carbon Leaf', activeWhen: '' },
        P2: { emoji: '🥶', alias: 'Sirius Chill preset', press: 'Music.Favorite:53 - SiriusXM Chill', activeWhen: '' },
        M1: { emoji: '⛵️', alias: 'Rockboat preset', press: 'Music.Favorite:Rockboat', activeWhen: '' },
        M2: { emoji: '😎', alias: 'Office DJ preset', press: 'Music.Favorite:Office DJ', activeWhen: '' },
        M3: { emoji: '🌌', alias: 'Zero 7 preset', press: 'Music.Favorite:Zero 7', activeWhen: '' },
        M4: { emoji: '💇🏻‍♂️', alias: 'Steve Aoki preset', press: "Music.Favorite:735 - Steve Aoki's Remix Radio", activeWhen: '' },
        RG: { emoji: '🌈', alias: 'LED rainbow', press: 'LedGrid.Start:rainbow', activeWhen: '' },
        SP: { emoji: '✨', alias: 'LED sparkle', press: 'LedGrid.Start:sparkle', activeWhen: '' },
        TT: { emoji: '🧱', alias: 'LED tetris', press: 'LedGrid.Start:tetris', activeWhen: '' },
        PL: { emoji: '▶️', alias: 'Play/pause toggle', press: 'Music.PlayPause', activeWhen: '' },
        PA: { emoji: '⏸', alias: 'Pause', press: 'Music.Pause', activeWhen: '' },
        SK: { emoji: '⏭', alias: 'Skip', press: 'Music.Next', activeWhen: '' },
        N1: { emoji: '🎶', alias: 'Banner anchor left', press: 'App.Refresh', activeWhen: '' },
        N2: { emoji: '🎶', alias: 'Banner anchor right', press: '', activeWhen: '' },
        ST: { emoji: '🔡', alias: 'Status banner cell', press: 'Music.FetchState', activeWhen: '' },
        CA: { emoji: '📅', alias: 'Calendar print preset', press: 'Printer.Preset:S3nysytjA14', activeWhen: '' },
    };

    var LAYOUTS = [
        {
            id: 'default',
            title: 'Default / iPhone Landscape',
            rows: 8,
            cols: 11,
            baseGrid: [
                ['..', 'BA', 'KI', 'BE', 'TE', 'RI', 'TV', 'GU', 'BR', '..', '..'],
                ['..', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', '..', '..'],
                ['..', '..', 'BU', 'BD', 'OU', 'OD', '..', 'LH', 'LM', 'LO', '..'],
                ['..', 'VU', '..', 'FI', '..', '..', 'P1', 'P2', '..', '..', '..'],
                ['..', 'VM', '..', '..', '..', 'M1', 'M2', 'M3', 'M4', '..', '..'],
                ['..', 'VD', '..', '..', '..', '..', '..', '..', '..', '..', '..'],
                ['..', '..', '..', 'PL', '..', 'PA', '..', 'SK', '..', '..', '..'],
                ['N1', 'ST', 'ST', 'ST', 'ST', 'ST', 'ST', 'ST', 'ST', 'ST', 'N2'],
            ],
            variants: {
                base: {},
                living_room: {
                    title: 'Living Room',
                    patches: {
                        '5,6': { token: 'RG', overrideScope: 'Living Room' },
                        '5,7': { token: 'SP', overrideScope: 'Living Room' },
                        '5,8': { token: 'TT', overrideScope: 'Living Room' },
                    },
                },
                kitchen: {
                    title: 'Kitchen',
                    patches: {
                        '2,10': { token: 'CA', overrideScope: 'Kitchen' },
                        '5,6': { token: 'RG', overrideScope: 'Kitchen' },
                        '5,7': { token: 'SP', overrideScope: 'Kitchen' },
                        '5,8': { token: 'TT', overrideScope: 'Kitchen' },
                    },
                },
            },
        },
        {
            id: 'iphone_portrait',
            title: 'iPhone Portrait',
            rows: 12,
            cols: 6,
            baseGrid: [
                ['BA', 'S1', 'M1', 'M2', 'M3', 'M4'],
                ['KI', 'S2', 'P1', 'P2', 'FI', '..'],
                ['BE', 'S3', '..', '..', '..', '..'],
                ['TE', 'S4', '..', '..', '..', '..'],
                ['RI', 'S5', '..', '..', '..', '..'],
                ['TV', 'S6', 'LH', 'LM', 'LO', 'VM'],
                ['GU', 'S7', 'PL', 'PA', 'SK', '..'],
                ['BR', 'S8', '..', '..', '..', 'N1'],
                ['..', '..', '..', '..', '..', '..'],
                ['..', '..', '..', '..', '..', '..'],
                ['..', '..', '..', '..', '..', '..'],
                ['..', '..', 'VU', 'ST', 'ST', 'VD'],
            ],
            variants: {
                base: {},
                living_room: {
                    title: 'Living Room',
                    patches: {
                        '2,3': { token: 'RG', overrideScope: 'Living Room' },
                        '2,4': { token: 'SP', overrideScope: 'Living Room' },
                        '2,5': { token: 'TT', overrideScope: 'Living Room' },
                    },
                },
                kitchen: {
                    title: 'Kitchen',
                    patches: {
                        '2,3': { token: 'RG', overrideScope: 'Kitchen' },
                        '2,4': { token: 'SP', overrideScope: 'Kitchen' },
                        '2,5': { token: 'TT', overrideScope: 'Kitchen' },
                        '3,5': { token: 'CA', overrideScope: 'Kitchen' },
                    },
                },
            },
        },
    ];

    var state = {
        selectedLayoutId: LAYOUTS[0].id,
        selectedVariantId: 'base',
        selectedCellKey: null,
        draggingCellKey: null,
        dropTargetCellKey: null,
        dragPointerId: null,
        pendingGridPointer: null,
        statusInteraction: null,
        undoStack: [],
        pendingInspectorSnapshot: false,
    };

    var els = {};

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function inspectorInputs() {
        return [
            els.cellToken,
            els.cellEmoji,
            els.cellAlias,
            els.cellPress,
            els.cellActiveWhen,
            els.cellOverrideScope,
            els.cellNotes,
        ];
    }

    function setSelectedCell(cellKey) {
        state.selectedCellKey = cellKey || null;
    }

    function clearTransientPointerState() {
        state.draggingCellKey = null;
        state.dropTargetCellKey = null;
        state.dragPointerId = null;
        state.pendingGridPointer = null;
        state.statusInteraction = null;
    }

    function resetInspectorSnapshotBoundary() {
        state.pendingInspectorSnapshot = false;
    }

    function takeSnapshot() {
        return {
            layouts: clone(runtimeLayouts),
            selectedLayoutId: state.selectedLayoutId,
            selectedVariantId: state.selectedVariantId,
            selectedCellKey: state.selectedCellKey,
        };
    }

    function pushUndoSnapshot() {
        state.undoStack.push(takeSnapshot());
        if (state.undoStack.length > 100) {
            state.undoStack.shift();
        }
    }

    function undoLastMutation() {
        var snapshot = state.undoStack.pop();
        if (!snapshot) {
            return;
        }
        runtimeLayouts = snapshot.layouts;
        state.selectedLayoutId = snapshot.selectedLayoutId;
        state.selectedVariantId = snapshot.selectedVariantId;
        setSelectedCell(snapshot.selectedCellKey);
        clearTransientPointerState();
        resetInspectorSnapshotBoundary();
        render();
    }

    function keyForCell(row, col) {
        return row + ',' + col;
    }

    function tokenMetadata(token) {
        return TOKEN_LIBRARY[token] || {
            emoji: '',
            alias: '',
            press: '',
            activeWhen: '',
        };
    }

    function createCell(row, col, token, overrides) {
        var meta = tokenMetadata(token);
        return Object.assign(
            {
                row: row,
                col: col,
                token: token,
                emoji: meta.emoji,
                alias: meta.alias,
                press: meta.press,
                activeWhen: meta.activeWhen,
                overrideScope: '',
                notes: '',
            },
            overrides || {}
        );
    }

    function createBaseCells(layout) {
        var cells = {};
        layout.baseGrid.forEach(function(rowTokens, rowIndex) {
            rowTokens.forEach(function(token, colIndex) {
                cells[keyForCell(rowIndex, colIndex)] = createCell(
                    rowIndex,
                    colIndex,
                    token
                );
            });
        });
        return cells;
    }

    function initializeLayouts() {
        return LAYOUTS.map(function(layout) {
            var initialized = clone(layout);
            initialized.baseCells = createBaseCells(layout);
            Object.keys(initialized.variants).forEach(function(variantId) {
                var variant = initialized.variants[variantId];
                var patches = variant.patches || {};
                Object.keys(patches).forEach(function(cellKey) {
                    var patch = patches[cellKey];
                    var token = patch.token || EMPTY_TOKEN;
                    patches[cellKey] = Object.assign(
                        createCell(-1, -1, token, {
                            overrideScope: variant.title || variantId,
                        }),
                        patch
                    );
                });
                variant.patches = patches;
            });
            return initialized;
        });
    }

    var runtimeLayouts = initializeLayouts();

    function currentLayout() {
        return runtimeLayouts.find(function(layout) {
            return layout.id === state.selectedLayoutId;
        });
    }

    function currentVariant() {
        var layout = currentLayout();
        return layout.variants[state.selectedVariantId];
    }

    function effectiveCells() {
        var layout = currentLayout();
        var variant = currentVariant();
        var cells = clone(layout.baseCells);

        if (variant && variant.patches) {
            Object.keys(variant.patches).forEach(function(cellKey) {
                cells[cellKey] = Object.assign({}, cells[cellKey], variant.patches[cellKey]);
            });
        }

        return cells;
    }

    function selectedEffectiveCell() {
        var cells = effectiveCells();
        return cells[state.selectedCellKey] || null;
    }

    function selectedPatchCell() {
        if (state.selectedVariantId === 'base') {
            return null;
        }
        var variant = currentVariant();
        return variant.patches[state.selectedCellKey] || null;
    }

    function currentEditableCell() {
        if (!state.selectedCellKey) {
            return null;
        }
        return editableCellForKey(state.selectedCellKey);
    }

    function editableCellForKey(cellKey) {
        var layout = currentLayout();
        if (!cellKey) {
            return null;
        }

        if (state.selectedVariantId === 'base') {
            return layout.baseCells[cellKey];
        }

        var variant = currentVariant();
        if (!variant.patches[cellKey]) {
            var baseCell = layout.baseCells[cellKey];
            variant.patches[cellKey] = Object.assign({}, baseCell, {
                overrideScope: variant.title || state.selectedVariantId,
            });
        }
        return variant.patches[cellKey];
    }

    function isSameCell(a, b) {
        return (
            a.token === b.token &&
            a.emoji === b.emoji &&
            a.alias === b.alias &&
            a.press === b.press &&
            a.activeWhen === b.activeWhen &&
            (a.notes || '') === (b.notes || '') &&
            (a.overrideScope || '') === (b.overrideScope || '')
        );
    }

    function cleanupSelectedPatch() {
        cleanupPatchForKey(state.selectedCellKey);
    }

    function cleanupPatchForKey(cellKey) {
        if (state.selectedVariantId === 'base' || !cellKey) {
            return;
        }
        var layout = currentLayout();
        var variant = currentVariant();
        var patch = variant.patches[cellKey];
        if (!patch) {
            return;
        }
        var baseCell = layout.baseCells[cellKey];
        if (isSameCell(patch, baseCell)) {
            delete variant.patches[cellKey];
        }
    }

    function assignCellValue(targetCell, sourceCell) {
        targetCell.token = sourceCell.token;
        targetCell.emoji = sourceCell.emoji;
        targetCell.alias = sourceCell.alias;
        targetCell.press = sourceCell.press;
        targetCell.activeWhen = sourceCell.activeWhen;
        targetCell.overrideScope = sourceCell.overrideScope || '';
        targetCell.notes = sourceCell.notes || '';
    }

    function swapCells(sourceKey, targetKey) {
        if (!sourceKey || !targetKey || sourceKey === targetKey) {
            return;
        }

        var cells = effectiveCells();
        var source = cells[sourceKey];
        var target = cells[targetKey];
        if (!source || !target) {
            return;
        }

        var sourceEditable = editableCellForKey(sourceKey);
        var targetEditable = editableCellForKey(targetKey);
        var sourceSnapshot = clone(source);
        var targetSnapshot = clone(target);

        assignCellValue(sourceEditable, targetSnapshot);
        assignCellValue(targetEditable, sourceSnapshot);

        cleanupPatchForKey(sourceKey);
        cleanupPatchForKey(targetKey);
    }

    function beginCellDrag(cellKey, pointerId) {
        state.draggingCellKey = cellKey;
        state.dropTargetCellKey = null;
        state.dragPointerId = pointerId;
        render();
    }

    function updateCellDragTargetFromPoint(clientX, clientY) {
        if (!state.draggingCellKey) {
            return;
        }
        var hovered = document.elementFromPoint(clientX, clientY);
        var button = hovered && hovered.closest('.editor-cell');
        state.dropTargetCellKey = button ? button.dataset.cellKey : null;
        render();
    }

    function finishCellDrag(cancelled) {
        var sourceKey = state.draggingCellKey;
        var targetKey = state.dropTargetCellKey;

        state.draggingCellKey = null;
        state.dropTargetCellKey = null;
        state.dragPointerId = null;

        if (!cancelled && sourceKey && targetKey && sourceKey !== targetKey) {
            pushUndoSnapshot();
            swapCells(sourceKey, targetKey);
            state.selectedCellKey = targetKey;
        }

        render();
    }

    function clearPendingGridPointer() {
        state.pendingGridPointer = null;
    }

    function commitMutation(mutator) {
        pushUndoSnapshot();
        mutator();
    }

    function startStatusResize(cellKey, direction, pointerId, clientX) {
        var run = statusRunForCell(cellKey);
        if (!run) {
            return;
        }
        state.statusInteraction = {
            type: 'resize',
            pointerId: pointerId,
            cellKey: cellKey,
            direction: direction,
            run: run,
            startX: clientX,
        };
    }

    function startStatusMove(cellKey, pointerId) {
        var run = statusRunForCell(cellKey);
        if (!run) {
            return;
        }
        state.statusInteraction = {
            type: 'move',
            pointerId: pointerId,
            cellKey: cellKey,
            run: run,
        };
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function statusRunMap(layout, cells) {
        var byFirstKey = {};
        var byCellKey = {};

        statusRuns(layout, cells).forEach(function(run) {
            byFirstKey[run.firstKey] = run;
            for (var col = run.startCol; col < run.startCol + run.length; col++) {
                byCellKey[keyForCell(run.row, col)] = run;
            }
        });

        return {
            byFirstKey: byFirstKey,
            byCellKey: byCellKey,
        };
    }

    function canOccupyStatusSpan(cells, row, startCol, length, originalRun) {
        var layout = currentLayout();
        if (startCol < 0 || length < 1 || startCol + length > layout.cols) {
            return false;
        }

        for (var col = startCol; col < startCol + length; col++) {
            var key = keyForCell(row, col);
            var withinOriginal =
                originalRun &&
                row === originalRun.row &&
                col >= originalRun.startCol &&
                col < originalRun.startCol + originalRun.length;
            if (withinOriginal) {
                continue;
            }
            if (cells[key].token !== EMPTY_TOKEN) {
                return false;
            }
        }
        return true;
    }

    function applyStatusSpan(originalRun, row, startCol, length) {
        var layout = currentLayout();
        var cells = effectiveCells();
        var sourceCell = cells[originalRun.firstKey];
        var sourceMeta = {
            row: row,
            col: startCol,
            token: 'ST',
            emoji: sourceCell.emoji || tokenMetadata('ST').emoji,
            alias: sourceCell.alias || tokenMetadata('ST').alias,
            press: sourceCell.press || tokenMetadata('ST').press,
            activeWhen: sourceCell.activeWhen || tokenMetadata('ST').activeWhen,
            overrideScope: sourceCell.overrideScope || '',
            notes: sourceCell.notes || '',
        };

        if (!canOccupyStatusSpan(cells, row, startCol, length, originalRun)) {
            return false;
        }

        for (var originalCol = originalRun.startCol;
             originalCol < originalRun.startCol + originalRun.length;
             originalCol++) {
            clearCell(keyForCell(originalRun.row, originalCol));
        }

        for (var targetCol = startCol; targetCol < startCol + length; targetCol++) {
            assignCellValue(
                editableCellForKey(keyForCell(row, targetCol)),
                Object.assign({}, sourceMeta, {
                    row: row,
                    col: targetCol,
                })
            );
        }

        for (var cleanupCol = 0; cleanupCol < layout.cols; cleanupCol++) {
            cleanupPatchForKey(keyForCell(originalRun.row, cleanupCol));
            cleanupPatchForKey(keyForCell(row, cleanupCol));
        }
        state.selectedCellKey = keyForCell(row, startCol);
        return true;
    }

    function finishStatusInteraction(event) {
        var interaction = state.statusInteraction;
        if (!interaction) {
            return false;
        }

        state.statusInteraction = null;

        if (interaction.type === 'resize') {
            var layout = currentLayout();
            var deltaCols = Math.round(
                (event.clientX - interaction.startX) / GRID_CELL_SIZE
            );
            var nextStart = interaction.run.startCol;
            var nextLength = interaction.run.length;

            if (interaction.direction === 'left') {
                nextStart = clamp(
                    interaction.run.startCol + deltaCols,
                    0,
                    interaction.run.startCol + interaction.run.length - 1
                );
                nextLength =
                    interaction.run.length + (interaction.run.startCol - nextStart);
            } else {
                nextLength = clamp(
                    interaction.run.length + deltaCols,
                    1,
                    layout.cols - interaction.run.startCol
                );
            }

            if (
                nextStart !== interaction.run.startCol ||
                nextLength !== interaction.run.length
            ) {
                commitMutation(function() {
                    applyStatusSpan(
                        interaction.run,
                        interaction.run.row,
                        nextStart,
                        nextLength
                    );
                });
            }

            render();
            return true;
        }

        if (interaction.type === 'move') {
            var hovered = document.elementFromPoint(event.clientX, event.clientY);
            var target =
                hovered &&
                (hovered.closest('.editor-cell') ||
                    hovered.closest('.editor-status-block'));
            if (!target) {
                render();
                return true;
            }

            var targetKey = target.dataset.cellKey;
            var cells = effectiveCells();
            var targetCell = cells[targetKey];
            if (!targetCell) {
                render();
                return true;
            }

            if (
                targetCell.row !== interaction.run.row ||
                targetCell.col !== interaction.run.startCol
            ) {
                commitMutation(function() {
                    applyStatusSpan(
                        interaction.run,
                        targetCell.row,
                        targetCell.col,
                        interaction.run.length
                    );
                });
            }

            render();
            return true;
        }

        return false;
    }

    function updateCellFromInputs() {
        var cell = currentEditableCell();
        if (!cell) {
            return;
        }
        if (!state.pendingInspectorSnapshot) {
            pushUndoSnapshot();
            state.pendingInspectorSnapshot = true;
        }

        cell.token = (els.cellToken.value || EMPTY_TOKEN).trim() || EMPTY_TOKEN;
        cell.emoji = els.cellEmoji.value.trim();
        cell.alias = els.cellAlias.value.trim();
        cell.press = els.cellPress.value.trim();
        cell.activeWhen = els.cellActiveWhen.value.trim();
        cell.overrideScope = els.cellOverrideScope.value.trim();
        cell.notes = els.cellNotes.value;

        cleanupSelectedPatch();
        render();
    }

    function resetSelectedPatch() {
        if (state.selectedVariantId === 'base' || !state.selectedCellKey) {
            return;
        }
        pushUndoSnapshot();
        var variant = currentVariant();
        delete variant.patches[state.selectedCellKey];
        render();
    }

    function clearCell(cellKey) {
        var editable = editableCellForKey(cellKey);
        if (!editable) {
            return;
        }
        var empty = tokenMetadata(EMPTY_TOKEN);
        editable.token = EMPTY_TOKEN;
        editable.emoji = empty.emoji;
        editable.alias = empty.alias;
        editable.press = empty.press;
        editable.activeWhen = empty.activeWhen;
        editable.notes = '';
        if (state.selectedVariantId !== 'base') {
            editable.overrideScope =
                editable.overrideScope || currentVariant().title || state.selectedVariantId;
        } else {
            editable.overrideScope = '';
        }
        cleanupPatchForKey(cellKey);
    }

    function setInspectorDisabled(disabled) {
        inspectorInputs().forEach(function(input) {
            input.disabled = disabled;
            if (disabled) {
                input.value = '';
            }
        });
    }

    function populateInspector(cell) {
        els.cellToken.value = cell.token || EMPTY_TOKEN;
        els.cellEmoji.value = cell.emoji || '';
        els.cellAlias.value = cell.alias || '';
        els.cellPress.value = cell.press || '';
        els.cellActiveWhen.value = cell.activeWhen || '';
        els.cellOverrideScope.value = cell.overrideScope || '';
        els.cellNotes.value = cell.notes || '';
    }

    function formatTokenGrid() {
        var layout = currentLayout();
        var cells = effectiveCells();
        var lines = [];

        for (var row = 0; row < layout.rows; row++) {
            var tokens = [];
            for (var col = 0; col < layout.cols; col++) {
                tokens.push(cells[keyForCell(row, col)].token || EMPTY_TOKEN);
            }
            lines.push(tokens.join(' '));
        }

        return lines.join('\n');
    }

    function formatVariantMetadata() {
        var layout = currentLayout();
        var variant = currentVariant();

        return JSON.stringify(
            {
                layout: layout.id,
                variant: state.selectedVariantId,
                patches: variant.patches,
            },
            null,
            2
        );
    }

    function legendEntries() {
        var cells = effectiveCells();
        return Object.keys(cells)
            .filter(function(cellKey) {
                return cells[cellKey].token && cells[cellKey].token !== EMPTY_TOKEN;
            })
            .sort(function(a, b) {
                var left = cells[a];
                var right = cells[b];
                if (left.row === right.row) {
                    return left.col - right.col;
                }
                return left.row - right.row;
            })
            .map(function(cellKey) {
                var cell = cells[cellKey];
                return {
                    cellKey: cellKey,
                    row: cell.row,
                    col: cell.col,
                    token: cell.token,
                    emoji: cell.emoji,
                    alias: cell.alias,
                };
            });
    }

    function scrollLegendToSelection() {
        if (!state.selectedCellKey) {
            return;
        }
        var selectedItem = els.legendList.querySelector(
            '[data-cell-key="' + state.selectedCellKey + '"]'
        );
        if (!selectedItem) {
            return;
        }

        var containerTop = els.legendList.scrollTop;
        var containerHeight = els.legendList.clientHeight;
        var itemTop = selectedItem.offsetTop;
        var itemBottom = itemTop + selectedItem.offsetHeight;

        if (itemTop < containerTop) {
            els.legendList.scrollTop = itemTop - 8;
            return;
        }

        if (itemBottom > containerTop + containerHeight) {
            els.legendList.scrollTop = itemBottom - containerHeight + 8;
        }
    }

    function renderLegend() {
        var fragment = document.createDocumentFragment();

        legendEntries().forEach(function(entry) {
            var item = document.createElement('div');
            item.className = 'legend-item';
            item.dataset.cellKey = entry.cellKey;
            if (state.selectedCellKey === entry.cellKey) {
                item.classList.add('is-selected');
            }

            var emoji = document.createElement('div');
            emoji.className = 'legend-emoji';
            emoji.textContent = entry.emoji || '·';

            var copy = document.createElement('div');
            copy.className = 'legend-copy';

            var token = document.createElement('div');
            token.className = 'legend-token';
            token.textContent =
                entry.token + '  r' + (entry.row + 1) + 'c' + (entry.col + 1);

            var label = document.createElement('div');
            label.className = 'legend-label';
            label.textContent = entry.alias || 'No alias';

            copy.appendChild(token);
            copy.appendChild(label);
            item.appendChild(emoji);
            item.appendChild(copy);
            fragment.appendChild(item);
        });

        els.legendList.innerHTML = '';
        els.legendList.appendChild(fragment);
        scrollLegendToSelection();
    }

    function statusRuns(layout, cells) {
        var runs = [];
        for (var row = 0; row < layout.rows; row++) {
            var start = null;
            var length = 0;
            for (var col = 0; col < layout.cols; col++) {
                var cell = cells[keyForCell(row, col)];
                if (cell && cell.token === STATUS_TOKEN) {
                    if (start === null) {
                        start = col;
                        length = 1;
                    } else {
                        length += 1;
                    }
                } else if (start !== null) {
                    runs.push({
                        row: row,
                        startCol: start,
                        length: length,
                        firstKey: keyForCell(row, start),
                    });
                    start = null;
                    length = 0;
                }
            }
            if (start !== null) {
                runs.push({
                    row: row,
                    startCol: start,
                    length: length,
                    firstKey: keyForCell(row, start),
                });
            }
        }
        return runs;
    }

    function statusRunForCell(cellKey, runMap) {
        if (!cellKey) {
            return null;
        }
        if (runMap && runMap.byCellKey) {
            return runMap.byCellKey[cellKey] || null;
        }

        var layout = currentLayout();
        var cells = effectiveCells();
        return statusRunMap(layout, cells).byCellKey[cellKey] || null;
    }

    function renderGrid() {
        var layout = currentLayout();
        var cells = effectiveCells();
        var variant = currentVariant();
        var runMap = statusRunMap(layout, cells);
        var skipped = {};

        els.gridPreview.innerHTML = '';
        els.gridPreview.style.gridTemplateColumns =
            'repeat(' + layout.cols + ', minmax(72px, 72px))';
        els.gridPreview.style.gridTemplateRows =
            'repeat(' + layout.rows + ', minmax(72px, 72px))';

        for (var row = 0; row < layout.rows; row++) {
            for (var col = 0; col < layout.cols; col++) {
                var cellKey = keyForCell(row, col);
                if (skipped[cellKey]) {
                    continue;
                }
                var cell = cells[cellKey];
                var run = runMap.byFirstKey[cellKey];

                if (run) {
                    var statusBlock = document.createElement('div');
                    statusBlock.className = 'editor-status-block';
                    statusBlock.dataset.cellKey = cellKey;
                    statusBlock.style.gridColumn =
                        String(run.startCol + 1) + ' / span ' + String(run.length);
                    statusBlock.style.gridRow = String(run.row + 1);
                    var selectedRun = statusRunForCell(state.selectedCellKey, runMap);
                    if (selectedRun && selectedRun.firstKey === cellKey) {
                        statusBlock.classList.add('is-selected');
                    }

                    var leftAnchor = document.createElement('div');
                    leftAnchor.className = 'editor-status-block__anchor';
                    leftAnchor.textContent = '🎶';

                    var viewport = document.createElement('div');
                    viewport.className = 'editor-status-block__viewport';

                    var track = document.createElement('div');
                    track.className = 'editor-status-block__track';

                    var textA = document.createElement('div');
                    textA.className = 'editor-status-block__text';
                    textA.textContent = 'Music title or intent state marquee';

                    var textB = document.createElement('div');
                    textB.className = 'editor-status-block__text';
                    textB.textContent = 'Music title or intent state marquee';

                    track.appendChild(textA);
                    track.appendChild(textB);
                    viewport.appendChild(track);

                    var rightAnchor = document.createElement('div');
                    rightAnchor.className = 'editor-status-block__anchor';
                    rightAnchor.textContent = '🎶';

                    var leftHandle = document.createElement('button');
                    leftHandle.type = 'button';
                    leftHandle.className =
                        'editor-status-block__handle editor-status-block__handle--left';
                    leftHandle.dataset.resizeDirection = 'left';

                    var rightHandle = document.createElement('button');
                    rightHandle.type = 'button';
                    rightHandle.className =
                        'editor-status-block__handle editor-status-block__handle--right';
                    rightHandle.dataset.resizeDirection = 'right';

                    statusBlock.appendChild(leftHandle);
                    statusBlock.appendChild(leftAnchor);
                    statusBlock.appendChild(viewport);
                    statusBlock.appendChild(rightAnchor);
                    statusBlock.appendChild(rightHandle);
                    els.gridPreview.appendChild(statusBlock);

                    for (var skipCol = run.startCol; skipCol < run.startCol + run.length; skipCol++) {
                        skipped[keyForCell(run.row, skipCol)] = true;
                    }
                    continue;
                }
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'editor-cell';
                button.draggable = false;

                if (state.selectedCellKey === cellKey) {
                    button.classList.add('is-selected');
                }
                if (cell.token === EMPTY_TOKEN) {
                    button.classList.add('is-empty');
                }
                if (variant.patches && variant.patches[cellKey]) {
                    button.classList.add('is-override');
                }
                if (state.draggingCellKey === cellKey) {
                    button.classList.add('is-dragging');
                }
                if (state.dropTargetCellKey === cellKey) {
                    button.classList.add('is-drop-target');
                }

                button.dataset.cellKey = cellKey;

                var emoji = document.createElement('div');
                emoji.className = 'editor-cell__emoji';
                emoji.textContent = cell.emoji || '';

                var token = document.createElement('div');
                token.className = 'editor-cell__token';
                token.textContent = cell.token;

                button.appendChild(emoji);
                button.appendChild(token);
                els.gridPreview.appendChild(button);
            }
        }
    }

    function renderInspector() {
        var cell = selectedEffectiveCell();
        var patch = selectedPatchCell();
        var variantTitle = currentVariant().title || 'Base';

        if (!cell) {
            els.selectionLabel.textContent = 'No cell selected.';
            setInspectorDisabled(true);
            els.resetCell.disabled = true;
            return;
        }

        setInspectorDisabled(false);

        els.selectionLabel.textContent =
            'Row ' +
            (cell.row + 1) +
            ', Col ' +
            (cell.col + 1) +
            ' in ' +
            variantTitle;

        populateInspector(cell);
        els.resetCell.disabled = state.selectedVariantId === 'base' || !patch;
    }

    function renderOutputs() {
        els.tokenGridOutput.value = formatTokenGrid();
        els.metadataOutput.value = formatVariantMetadata();
    }

    function populateLayoutSelect() {
        els.layoutSelect.innerHTML = runtimeLayouts
            .map(function(layout) {
                return (
                    '<option value="' +
                    layout.id +
                    '">' +
                    layout.title +
                    '</option>'
                );
            })
            .join('');
    }

    function populateVariantSelect() {
        var layout = currentLayout();

        els.variantSelect.innerHTML = Object.keys(layout.variants)
            .map(function(variantId) {
                var variant = layout.variants[variantId];
                var title = variant.title || 'Base';
                return (
                    '<option value="' +
                    variantId +
                    '">' +
                    title +
                    '</option>'
                );
            })
            .join('');
    }

    function updateHeader() {
        var layout = currentLayout();
        var variant = currentVariant();
        els.canvasTitle.textContent = layout.title;
        els.canvasSubtitle.textContent =
            'Editing ' + (variant.title || 'Base') + ' variant';
        els.undoButton.disabled = state.undoStack.length === 0;
    }

    function render() {
        populateVariantSelect();
        els.variantSelect.value = state.selectedVariantId;
        updateHeader();
        renderLegend();
        renderGrid();
        renderInspector();
        renderOutputs();
    }

    function attachEvents() {
        var formInputs = inspectorInputs();

        els.layoutSelect.addEventListener('change', function() {
            state.selectedLayoutId = els.layoutSelect.value;
            state.selectedVariantId = 'base';
            setSelectedCell(null);
            render();
        });

        els.variantSelect.addEventListener('change', function() {
            state.selectedVariantId = els.variantSelect.value;
            setSelectedCell(null);
            render();
        });

        els.gridPreview.addEventListener('click', function(event) {
            if (event.target.closest('.editor-status-block__handle')) {
                return;
            }
            var statusBlock = event.target.closest('.editor-status-block');
            if (statusBlock) {
                setSelectedCell(statusBlock.dataset.cellKey);
                render();
                return;
            }
            var button = event.target.closest('.editor-cell');
            if (!button) {
                return;
            }
            setSelectedCell(button.dataset.cellKey);
            render();
        });

        els.gridPreview.addEventListener('pointerdown', function(event) {
            var handle = event.target.closest('.editor-status-block__handle');
            if (handle) {
                event.preventDefault();
                var block = handle.closest('.editor-status-block');
                if (!block) {
                    return;
                }
                setSelectedCell(block.dataset.cellKey);
                startStatusResize(
                    block.dataset.cellKey,
                    handle.dataset.resizeDirection,
                    event.pointerId,
                    event.clientX
                );
                return;
            }

            var statusBlock = event.target.closest('.editor-status-block');
            if (statusBlock) {
                setSelectedCell(statusBlock.dataset.cellKey);
                state.pendingGridPointer = {
                    pointerId: event.pointerId,
                    cellKey: statusBlock.dataset.cellKey,
                    mode: 'status-move',
                    startX: event.clientX,
                    startY: event.clientY,
                };
                return;
            }

            var cell = event.target.closest('.editor-cell');
            if (cell) {
                state.pendingGridPointer = {
                    pointerId: event.pointerId,
                    cellKey: cell.dataset.cellKey,
                    mode: 'cell-drag',
                    startX: event.clientX,
                    startY: event.clientY,
                };
            }
        });

        window.addEventListener('pointermove', function(event) {
            if (state.pendingGridPointer &&
                state.pendingGridPointer.pointerId === event.pointerId) {
                var deltaX = event.clientX - state.pendingGridPointer.startX;
                var deltaY = event.clientY - state.pendingGridPointer.startY;
                var distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
                if (distance >= POINTER_DRAG_THRESHOLD) {
                    if (state.pendingGridPointer.mode === 'status-move') {
                        startStatusMove(
                            state.pendingGridPointer.cellKey,
                            state.pendingGridPointer.pointerId
                        );
                    } else {
                        beginCellDrag(
                            state.pendingGridPointer.cellKey,
                            state.pendingGridPointer.pointerId
                        );
                    }
                    clearPendingGridPointer();
                }
            }
            if (state.statusInteraction &&
                state.statusInteraction.pointerId === event.pointerId) {
                event.preventDefault();
                return;
            }
            if (!state.draggingCellKey || state.dragPointerId !== event.pointerId) {
                return;
            }
            event.preventDefault();
            updateCellDragTargetFromPoint(event.clientX, event.clientY);
        });

        window.addEventListener('pointerup', function(event) {
            if (state.pendingGridPointer &&
                state.pendingGridPointer.pointerId === event.pointerId) {
                setSelectedCell(state.pendingGridPointer.cellKey);
                clearPendingGridPointer();
                render();
                return;
            }
            if (state.statusInteraction &&
                state.statusInteraction.pointerId === event.pointerId) {
                event.preventDefault();
                finishStatusInteraction(event);
                return;
            }
            if (!state.draggingCellKey || state.dragPointerId !== event.pointerId) {
                return;
            }
            event.preventDefault();
            finishCellDrag(false);
        });

        window.addEventListener('pointercancel', function(event) {
            if (state.pendingGridPointer &&
                state.pendingGridPointer.pointerId === event.pointerId) {
                clearPendingGridPointer();
                render();
                return;
            }
            if (state.statusInteraction &&
                state.statusInteraction.pointerId === event.pointerId) {
                state.statusInteraction = null;
                render();
                return;
            }
            if (!state.draggingCellKey || state.dragPointerId !== event.pointerId) {
                return;
            }
            finishCellDrag(true);
        });

        els.legendList.addEventListener('click', function(event) {
            var item = event.target.closest('.legend-item');
            if (!item) {
                return;
            }
            setSelectedCell(item.dataset.cellKey);
            render();
        });

        els.legendList.addEventListener('mousedown', function(event) {
            if (event.target.closest('.legend-item')) {
                event.preventDefault();
            }
        });

        formInputs.forEach(function(input) {
            input.addEventListener('focus', function() {
                resetInspectorSnapshotBoundary();
            });
            input.addEventListener('blur', function() {
                resetInspectorSnapshotBoundary();
            });
        });

        formInputs.forEach(function(input) {
            input.addEventListener('input', updateCellFromInputs);
        });

        els.resetCell.addEventListener('click', resetSelectedPatch);
        els.undoButton.addEventListener('click', undoLastMutation);

        document.addEventListener('keydown', function(event) {
            var target = event.target;
            var isTypingTarget =
                target &&
                (target.tagName === 'INPUT' ||
                    target.tagName === 'TEXTAREA' ||
                    target.isContentEditable);

            if ((event.key === 'Backspace' || event.key === 'Delete') &&
                state.selectedCellKey &&
                !isTypingTarget) {
                event.preventDefault();
                pushUndoSnapshot();
                clearCell(state.selectedCellKey);
                render();
                return;
            }

            if ((event.metaKey || event.ctrlKey) && !event.shiftKey &&
                event.key.toLowerCase() === 'z') {
                event.preventDefault();
                undoLastMutation();
            }
        });
    }

    function captureElements() {
        els.layoutSelect = document.getElementById('layout-select');
        els.variantSelect = document.getElementById('variant-select');
        els.legendList = document.getElementById('legend-list');
        els.gridPreview = document.getElementById('grid-preview');
        els.canvasTitle = document.getElementById('canvas-title');
        els.canvasSubtitle = document.getElementById('canvas-subtitle');
        els.selectionLabel = document.getElementById('selection-label');
        els.cellToken = document.getElementById('cell-token');
        els.cellEmoji = document.getElementById('cell-emoji');
        els.cellAlias = document.getElementById('cell-alias');
        els.cellPress = document.getElementById('cell-press');
        els.cellActiveWhen = document.getElementById('cell-active-when');
        els.cellOverrideScope = document.getElementById('cell-override-scope');
        els.cellNotes = document.getElementById('cell-notes');
        els.resetCell = document.getElementById('reset-cell');
        els.tokenGridOutput = document.getElementById('token-grid-output');
        els.metadataOutput = document.getElementById('metadata-output');
        els.undoButton = document.getElementById('undo-button');
    }

    function start() {
        captureElements();
        populateLayoutSelect();
        els.layoutSelect.value = state.selectedLayoutId;
        attachEvents();
        render();
    }

    document.addEventListener('DOMContentLoaded', start);
})();
