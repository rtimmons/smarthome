#!/usr/bin/python
# External module imports
from py_irsend import irsend
import cgi
import cgitb
import sys
import json

cgitb.enable()

body = sys.stdin.read()
#sys.stderr.write(body)
jsondata = json.loads(body)

try:
    state = jsondata["request"]["intent"]["slots"]["state"]["resolutions"]["resolutionsPerAuthority"][0]["values"][0]["value"]["id"]
    if state == "0":
        irsend.send_once('screen', ['KEY_0'])
    if state == "1":
        irsend.send_once('screen', ['KEY_2'])
except:
    print 'Content-Type: application/json;charset=UTF-8\n\n{"version":"1.0","response": {"outputSpeech": {"type":"PlainText","text":"I could not understand the direction."},"shouldEndSession":true}}'
    
#print jsondata
#sys.stderr.write(jsondata.request)

if state == "0":
    irsend.send_once('screen', ['KEY_0'])
if state == "1":
    irsend.send_once('screen', ['KEY_2'])

print 'Content-Type: application/json;charset=UTF-8\n\n{"version":"1.0","response": {"outputSpeech": {"type":"PlainText","text":"Yas Queen"},"shouldEndSession":true}}'
#print jsondata["request"]["intent"]["slots"]["state"]["value"]
