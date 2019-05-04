// This file is generated/overwritten by ansible for 'production' use.
// When iterating on development you can manually specify these values here.
const secrets = {
  hue: {
    bridge_ip: 'TODO',
    username: 'TODO',
  },
};

if (typeof module !== 'undefined') {
  module.exports = secrets;
}