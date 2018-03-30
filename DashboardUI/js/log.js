// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = $('#log');
    logger.hide();

    var lastLog = null;
    console.log = function () {
        var args = Array.prototype.slice.call(arguments);
        old(args);
        args = args.map(x => typeof x == 'object'
            ? JSON.stringify(x) : new String(x)
        ).join(' ');

        // don't warn the same thing multiple times
        if (args == lastLog) {
            return;
        }
        lastLog = args;

        logger.stop();
        logger.html(args);
        logger.fadeIn(20).promise().then(() => logger.fadeOut(1500));
    }
})();
