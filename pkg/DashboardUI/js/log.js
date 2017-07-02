// https://stackoverflow.com/questions/20256760/javascript-console-log-to-html

(function () {
    var old = console.log;
    var logger = document.getElementById('log');
    console.log = function () {
      var args = Array.prototype.slice.call(arguments);
        if (typeof args[0] == 'object') {
            logger.innerHTML += (JSON && JSON.stringify ? JSON.stringify(args[0]) : arguments) + '<br />';
        } else {
            logger.innerHTML += args.join(' ') + '<br />';
        }
        old(arguments);
    }
})();