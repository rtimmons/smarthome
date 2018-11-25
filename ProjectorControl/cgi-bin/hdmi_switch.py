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
input = int(arguments["input"].value)

if input == 1:
    irsend.send_once('hdmi_switch', ['KEY_1'])
if input == 2:
    irsend.send_once('hdmi_switch', ['KEY_2'])
if input == 3:
    irsend.send_once('hdmi_switch', ['KEY_3'])

print 'Content-Type: application/json;charset=UTF-8\n\n{"success":true}'