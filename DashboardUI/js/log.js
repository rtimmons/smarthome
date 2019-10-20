(function(win) {
    var old = console.error;
    console.error = function() {
        var args = Array.prototype.slice.call(arguments);
        old(args);
        $.post(`http://${win.secret.host.hostname}:3000/report`, { msg: args });
    };
})(window);
