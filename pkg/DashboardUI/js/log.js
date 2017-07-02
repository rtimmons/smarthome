// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = document.getElementById('log');
    console.log = function () {
        var args = Array.prototype.slice.call(arguments);
        args = args.map(x => typeof x == 'object'
            ? JSON.stringify(x) : new String(x)
        );
        logger.innerHTML = args.join(' ');
        old(arguments);
    }
})();