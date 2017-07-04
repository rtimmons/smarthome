// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = $('#log');
    logger.hide();
    console.log = function () {
        var args = Array.prototype.slice.call(arguments);
        old(args);
        args = args.map(x => typeof x == 'object'
            ? JSON.stringify(x) : new String(x)
        );
        logger.html(args.join(' '));
        logger.fadeIn(20).promise().then(() => logger.fadeOut(1500));
    }
})();