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
state = int(arguments["state"].value)

# Program: 

pi.write(pumpRelay, state)
print '<p>Successfully changed pump to "' + str(state) +'"</p>'

pi.stop()
