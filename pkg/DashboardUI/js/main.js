$(() => {
  $('td[data-urls]').click(function(e) {
    var t = $(this);
    var old = t.clone(true);
    t.html('🤔')
    var urls = t.data('urls').split(/\s+/)
    urls.forEach((url) => {
      $.get(url, {}, (resp) => { console.log(url, resp); t.replaceWith(old) });
    });
  });
});