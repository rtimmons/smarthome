'use strict';

const PANDORA_ENDPOINT = 'https://tuner.pandora.com/services/json/';

const DEFAULT_PARTNER = {
  username: 'android',
  password: 'AC7IBG09A3DTSYM4R41UJWL07VLN8JI7',
  deviceModel: 'android-generic',
  decryptPassword: 'R=U!LH$O2B#',
  encryptPassword: '6#26FRL$ZWD'
};

let blowfishModule;

async function getBlowfish() {
  if (!blowfishModule) {
    blowfishModule = import('egoroof-blowfish');
  }
  return blowfishModule;
}

function seconds() {
  return Math.floor(Date.now() / 1000);
}

async function encrypt(password, plaintext) {
  const { Blowfish } = await getBlowfish();
  const cipher = new Blowfish(password, Blowfish.MODE.ECB, Blowfish.PADDING.NULL);
  const input = Buffer.from(plaintext, 'utf8');
  const paddingLength = (16 - (input.length % 16)) % 16;
  const paddedInput = paddingLength === 0
    ? input
    : Buffer.concat([input, Buffer.alloc(paddingLength)]);
  return Buffer.from(cipher.encode(paddedInput));
}

async function decrypt(password, ciphertext) {
  const { Blowfish } = await getBlowfish();
  const cipher = new Blowfish(password, Blowfish.MODE.ECB, Blowfish.PADDING.NULL);
  return Buffer.from(cipher.decode(ciphertext, Blowfish.TYPE.UINT8_ARRAY));
}

async function pandoraRequest(method, query, body) {
  const endpoint = new URL(PANDORA_ENDPOINT);
  endpoint.searchParams.set('method', method);
  Object.keys(query || {}).forEach((key) => endpoint.searchParams.set(key, query[key]));

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body
  });
  if (!response.ok) {
    throw new Error(`Pandora request ${method} failed with HTTP ${response.status}`);
  }

  const parsed = await response.json();
  if (parsed.stat === 'fail') {
    throw new Error(`${parsed.message} [${parsed.code}]`);
  }
  if (parsed.stat !== 'ok') {
    throw new Error(`Pandora request ${method} returned an unknown response`);
  }
  return parsed.result;
}

function withCallback(promise, callback) {
  promise.then((result) => callback(null, result), callback);
}

class Anesidora {
  constructor(username, password, partnerInfo) {
    this.username = username;
    this.password = password;
    this.partnerInfo = Object.assign({}, partnerInfo || DEFAULT_PARTNER, { version: '5' });
    this.authData = null;
  }

  login(callback) {
    withCallback(this.loginAsync(), callback);
  }

  async loginAsync() {
    const partnerBody = Object.assign({}, this.partnerInfo);
    delete partnerBody.decryptPassword;
    delete partnerBody.encryptPassword;

    const partner = await pandoraRequest(
      'auth.partnerLogin',
      {},
      JSON.stringify(partnerBody)
    );
    const syncTime = await decrypt(
      this.partnerInfo.decryptPassword,
      Buffer.from(partner.syncTime, 'hex')
    );
    partner.syncTimeOffset = parseInt(syncTime.toString('utf8', 4, 14), 10) - seconds();

    const loginBody = await encrypt(this.partnerInfo.encryptPassword, JSON.stringify({
      loginType: 'user',
      username: this.username,
      password: this.password,
      partnerAuthToken: partner.partnerAuthToken,
      syncTime: partner.syncTimeOffset + seconds()
    }));
    const user = await pandoraRequest('auth.userLogin', {
      auth_token: partner.partnerAuthToken,
      partner_id: partner.partnerId
    }, loginBody.toString('hex').toLowerCase());

    this.authData = {
      userAuthToken: user.userAuthToken,
      partnerId: partner.partnerId,
      userId: user.userId,
      syncTimeOffset: partner.syncTimeOffset
    };
  }

  request(method, data, callback) {
    if (typeof data === 'function') {
      callback = data;
      data = {};
    }
    withCallback(this.requestAsync(method, data || {}), callback);
  }

  async requestAsync(method, data) {
    if (!this.authData) {
      throw new Error('Not authenticated with Pandora (call login() before request())');
    }

    const body = Object.assign({}, data, {
      userAuthToken: this.authData.userAuthToken,
      syncTime: this.authData.syncTimeOffset + seconds()
    });
    const encryptedBody = method === 'test.checkLicensing'
      ? undefined
      : (await encrypt(this.partnerInfo.encryptPassword, JSON.stringify(body)))
        .toString('hex')
        .toLowerCase();

    return pandoraRequest(method, {
      auth_token: this.authData.userAuthToken,
      partner_id: this.authData.partnerId,
      user_id: this.authData.userId
    }, encryptedBody);
  }
}

module.exports = Anesidora;
