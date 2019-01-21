#!/usr/bin/python
# External module imports
from py_irsend import irsend
import cgi
import cgitb
import sys
import json
import time

cgitb.enable()

# Query Params:
arguments = cgi.FieldStorage()
state = int(arguments["state"].value)

if state == 0:
    irsend.send_once('projector', ['KEY_POWER2'])
    time.sleep(1)
    irsend.send_once('projector', ['KEY_POWER2'])
if state == 1:
    irsend.send_once('projector', ['KEY_POWER'])

print 'Content-Type: application/json;charset=UTF-8\n\n{"success":true}'