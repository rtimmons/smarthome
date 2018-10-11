{"buttons":[
    {
       "name": "Play NPR",
       "address": "74:c2:46:96:37:75",
        "protocol": "arp",	
        "url": "http://localhost:5005/preset/playnpr",
        "method": "GET"
    },
    {
	"name": "Poop TV Input 1",
	"address": "34:d2:70:cd:b0:37",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/preset/all-tv",
	"method": "GET"
    },
    {
	"name": "Poop TV Input 2",
	"address": "0c:47:c9:22:ef:aa",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/preset/all-tv",
	"method": "GET"
    },
    {
	"name": "Mr Irrigation On",
	"address": "fc:65:de:62:27:28",
	"timeout": "5000",
	"protocol": "udp",
	"url": "http://grovepi.local/GrovePi/cgi-bin/state.py?zone=misters&state=0",
	"method": "GET"
    },
    {
	"name": "Mr Irrigation Off",
	"address": "00:fc:8b:17:3d:27",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://grovepi.local/GrovePi/cgi-bin/state.py?zone=misters&state=1",
	"method": "GET"
    },
    {
	"name": "Cafe Lights On",
	"address": "00:fc:8b:5c:43:40",
	"timeout": "120000",
	"protocol": "arp",
	"url": "https://maker.ifttt.com/trigger/cafe_on/with/key/lvbDNOTOAb59aoavCToJE",
	"method": "GET"
    },
    {
    "name": "Cafe Lights Off",
    "address": "8c:85:90:4e:ff:d5",
    "timeout": "120000",
    "protocol": "arp",
    "url": "https://maker.ifttt.com/trigger/cafe_off/with/key/lvbDNOTOAb59aoavCToJE",
    "method": "GET"
    },
    {
	"name": "Michael Standup",
	"address": "00:fc:8b:17:3d:27",
	"timeout": "120000",
	"protocol": "arp",
	"url": "https://maker.ifttt.com/trigger/standup_closet/with/key/lvbDNOTOAb59aoavCToJE",
	"method": "GET"
    },
    {
	"name": "Michael Standup",
	"address": "00:fc:8b:17:3d:27",
	"timeout": "120000",
	"protocol": "arp",
	"url": "https://maker.ifttt.com/trigger/standup_hue/with/key/lvbDNOTOAb59aoavCToJE",
	"method": "GET"
    },
    {
	"name": "Michael Standup",
	"address": "00:fc:8b:17:3d:27",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/pauseall",
	"method": "GET"
    }
]}