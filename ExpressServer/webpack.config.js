const path = require('path');
const webpack = require('webpack');

module.exports = {
  entry: './src/public/js/main.js',
  output: {
    path: path.resolve(__dirname, 'dist/'),
    filename: 'index.js'
  },
  mode: 'development',
  devServer: {
    contentBase: path.resolve(__dirname, 'src'),
    publicPath: '/dist/',
    watchContentBase: false,
    hotOnly: true
  },
  plugins: [
    new webpack.NamedModulesPlugin(),
    new webpack.HotModuleReplacementPlugin()
  ]
};
