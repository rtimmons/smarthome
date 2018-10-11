#!/usr/bin/python
# External module imports
import pigpio
import time
import cgi
import cgitb
import json

cgitb.enable()

print 'Content-type: text/html\n\n'
print '<h1>Zone Controller</h1>'

pi = pigpio.pi()

with open("gpio_mappings.json") as jsonfile:
     gpio_mappings = json.load(jsonfile)
     zone_dir_pins = gpio_mappings["zone_dir_pins"]
     zone_pulse_pins = gpio_mappings["zone_pulse_pins"]
     
     # Pin Setup:
     for i in zone_dir_pins.keys():
          pi.set_mode(zone_dir_pins[i],  pigpio.OUTPUT)
     for i in zone_pulse_pins.keys():
          pi.set_mode(zone_pulse_pins[i],  pigpio.OUTPUT)
          
     # Query Params:
     arguments = cgi.FieldStorage()
     zone = arguments["zone"].value
     minutes = int(arguments["minutes"].value)

     # Pin Selection:
     dir_pin = zone_dir_pins[zone]
     pulse_pin = zone_pulse_pins[zone]

     # Program:
     pi.write(dir_pin, 1)
     time.sleep(1)
     pi.write(pulse_pin, 1)
     time.sleep(1)
     pi.write(pulse_pin, 0)

     time.sleep(minutes * 60)
     
     pi.write(dir_pin, 0)
     time.sleep(1)
     pi.write(pulse_pin, 1)
     time.sleep(1)
     pi.write(pulse_pin, 0)
     print '<p>Successfully ran zone "' + zone + '" for ' + str(minutes) +' minutes</p>'

pi.stop()
