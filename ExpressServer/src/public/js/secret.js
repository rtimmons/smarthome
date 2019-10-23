// This file is bogus and will be overwritten by ansible
// It's just here so this thing can be run offline without
// going through a deploy phase

var secret = {
    host: {
        hostname: `${window.location.host || 'smarterhome.local:3000'}`,
    },
    ifttt: {
        key: 'DUMMY_DO_ANSIBLE_DEPLOY',
    },
};
