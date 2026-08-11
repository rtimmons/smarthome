'use strict';

async function request(options) {
  const url = options.url || options.uri;
  const headers = Object.assign({}, options.headers);
  let body = options.body;

  if (options.form) {
    body = new URLSearchParams(options.form).toString();
    if (!headers['Content-Type']) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
  }

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers,
    body
  });
  if (!response.ok) {
    const error = new Error(`Request to ${url} failed with HTTP ${response.status}`);
    error.statusCode = response.status;
    throw error;
  }

  return options.json ? response.json() : response.text();
}

module.exports = request;
