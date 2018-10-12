#!/usr/bin/python
# External module imports
from py_irsend import irsend
import cgi
import cgitb
import sys
import json

cgitb.enable()

# Query Params:
arguments = cgi.FieldStorage()
state = int(arguments["state"].value)

if state == 0:
    irsend.send_once('screen', ['KEY_0'])
if state == 1:
    irsend.send_once('screen', ['KEY_2'])

print 'Content-Type: application/json;charset=UTF-8\n\n{"success":true}'
