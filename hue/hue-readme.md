# Hue Integration

Register for Developer account here:
https://developers.meethue.com/login/?

Unofficial Docs:
https://www.burgestrand.se/hue-api/

Real Docs:
https://developers.meethue.com/develop/hue-api/groupds-api/

Press link button then run this:

```sh
BASE="http://192.168.1.11"
curl -X POST \
     -H "Content-Type: application/json" \
     -d '@in-register.json' \
     -o './out-register.json' \
     "$BASE/api"
```

Get full state:

```sh
BASE="http://192.168.1.11"
APPID="$(jq --raw-output '.[0].success.username' out-register.json)"
curl "$BASE/api/$APPID" -o ./out-state.json
```

Set a scene:

```sh
BASE="http://192.168.1.11"
APPID="$(jq --raw-output '.[0].success.username' out-register.json)"
curl \
    -X PUT \
    -d '{"scene":"PWs1grIjUuo1mA6"}' \
    "$BASE/api/$APPID/groups/1/action"
```

