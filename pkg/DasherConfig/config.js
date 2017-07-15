{"buttons":[
  {
    "name": "Play NPR",
    "address": "74:c2:46:96:37:75",
    "protocol": "arp",	
    "url": "http://retropie:5005/TV%20Room/preset/playnpr",
    "method": "GET"
  },
  {
      "name": "IFTTT",
      "address": "74:c2:46:96:37:75",
      "timeout": "60000",
      "protocol": "udp",
      "url": "http://maker.ifttt.com/trigger/PlayNPR/with/key/cLNpbWpb3jYP550-Mna27W",
      "method": "POST",
      "json": true,
      "body": {"value1": "any value"}
  }
]}