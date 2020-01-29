#!/usr/bin/python
# External module imports
import pigpio
import time
import cgi
import cgitb

cgitb.enable()

print('Content-type: text/html\n\n')
print('<h1>Python Script Test</h1>')

pi = pigpio.pi()

# Pin Definitons:
upRelay = 24
downRelay = 22
midRelay = 26
arguments = cgi.FieldStorage()
direction = arguments["direction"].value

# Pin Setup:

pi.set_mode(upRelay,  pigpio.OUTPUT)
pi.set_mode(downRelay,  pigpio.OUTPUT)
pi.set_mode(midRelay,  pigpio.OUTPUT)

# Program:

if(direction=="Up"):
    pi.write(upRelay, 1)
    time.sleep(1)
    pi.write(upRelay, 0)

if(direction=="Down"):
    pi.write(downRelay, 1)
    time.sleep(1)
    pi.write(downRelay, 0)

if(direction=="Mid"):
    pi.write(midRelay, 1)
    time.sleep(4)
    pi.write(midRelay, 0)

pi.stop()