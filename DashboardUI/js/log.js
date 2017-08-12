'use strict';

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) { return typeof obj; } : function (obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; };

// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = $('#log');
    logger.hide();
    console.log = function () {
        var args = Array.prototype.slice.call(arguments);
        old(args);
        args = args.map(function (x) {
            return (typeof x === 'undefined' ? 'undefined' : _typeof(x)) == 'object' ? JSON.stringify(x) : new String(x);
        });
        logger.html(args.join(' '));
        logger.fadeIn(20).promise().then(function () {
            return logger.fadeOut(1500);
        });
    };
})();