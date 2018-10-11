#!/usr/bin/python
# External module imports
from w1thermsensor import W1ThermSensor
import cgi
import cgitb
import json
import requests

#smartthings client id and client secret
client = '24e3a2c7-88b3-460b-839f-4abe51a65992'
access_token='b81f79c2-2ff5-4b26-97e9-47b6bacbf707'

cgitb.enable()

print 'Content-type: application/json\n'

sensor = W1ThermSensor()
temperature_in_fahrenheit = sensor.get_temperature(W1ThermSensor.DEGREES_F)

print int(temperature_in_fahrenheit)

endpoints_url = "https://graph.api.smartthings.com/api/smartapps/endpoints/%s?access_token=%s" % (client, access_token)
r = requests.get(endpoints_url)
if (r.status_code != 200):
   print("Error: " + r.status_code)
else:
   theendpoints = json.loads( r.text )
   for endp in theendpoints:
      uri = endp['uri']
      temp_url = uri + ("/update/%.2f/F" % temperature_in_fahrenheit)
      headers = { 'Authorization' : 'Bearer ' + access_token }
      r = requests.put(temp_url, headers=headers)