const path = require('path');

module.exports = {
  entry: './src/public/js/main.js',
  output: {
    path: path.resolve(__dirname, 'dist/'),
    filename: 'index.js'
  },
  mode: 'none'
};
