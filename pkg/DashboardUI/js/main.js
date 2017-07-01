$(() => {
  $('td[data-urls]').click(function(e) {
    var urls = $(this).data('urls').split(/\s+/)
    urls.forEach((url) => {
      $.get(url, {}, (resp) => $(this).html(resp));
    });
  });
});