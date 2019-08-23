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
	"url": "http://localhost:5005/preset/living-tv",
	"method": "GET"
    },
    {
	"name": "Poop TV Input 2",
	"address": "0c:47:c9:22:ef:aa",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/preset/living-tv",
	"method": "GET"
    },
    {
	"name": "Mister Spa Button",
	"address": "fc:65:de:62:27:28",
	"timeout": "5000",
	"protocol": "udp",
	"url": "http://192.168.1.40/cgi-bin/toggle.py?zone=misters",
	"method": "GET"
    },
    {
	"name": "Michael Work Music",
	"address": "00:fc:8b:9f:90:c2",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/preset/michaelwork",
	"method": "GET"
    },
    {
	"name": "Mute Button",
	"address": "00:fc:8b:5c:43:40",
	"timeout": "120000",
	"protocol": "arp",
	"url": "http://localhost:5005/pauseall",
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