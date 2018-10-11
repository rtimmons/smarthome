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
dirRelay  = 17
pwrRelay = 27

# Pin Setup:

pi.set_mode(dirRelay,  pigpio.OUTPUT)
pi.set_mode(pwrRelay,  pigpio.OUTPUT)

# Program: 

pi.write(dirRelay, 0)
time.sleep(1)
pi.write(pwrRelay, 1)
time.sleep(1)
pi.write(pwrRelay, 0)

pi.write(dirRelay, 0)

pi.stop()
