// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = $('#log');
    logger.hide();

    var lastLog = new Date().getTime();
    console.log = function () {
        var args = Array.prototype.slice.call(arguments);
        old(args);
        try {
          args = args.map(x => typeof x == 'object'
              ? JSON.stringify(x) : new String(x)
          ).join(' ');
        } catch(e) { }

        // don't write to screen too often
        if (new Date().getTime() - 2000 < lastLog) {
            return;
        }
        lastLog = new Date().getTime();

        logger.stop(true, true);
        logger.html(args);
        logger.fadeIn(20).promise().then(() => logger.fadeOut(1500));
    }
})();
