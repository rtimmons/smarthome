#!/usr/bin/python
# External module imports
import pigpio
import time
import cgi
import cgitb

cgitb.enable()

print 'Content-type: text/html\n\n'
print '<h1>Python Script Test</h1>'

pi = pigpio.pi()

# Pin Definitons:
pumpRelay = 21

# Pin Setup:
pi.set_mode(pumpRelay,  pigpio.OUTPUT)

# Query Params:
arguments = cgi.FieldStorage()
minutes = int(arguments["minutes"].value)

# Program: 
pi.write(pumpRelay, 1)
time.sleep(minutes*60)
pi.write(pumpRelay, 0)

pi.stop()
