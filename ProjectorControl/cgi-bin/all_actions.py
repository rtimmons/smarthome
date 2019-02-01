#!/usr/bin/python
# External module imports
from py_irsend import irsend
import cgi
import cgitb
import sys
import json
import time

cgitb.enable()
arguments = cgi.FieldStorage()
# HDMI switcher
if arguments.has_key("hdmi_input"):
    hdmi_input = int(arguments["hdmi_input"].value)

    if hdmi_input == 1:
        irsend.send_once('hdmi_switch', ['KEY_1'])
    if hdmi_input == 2:
        irsend.send_once('hdmi_switch', ['KEY_2'])
    if hdmi_input == 3:
        irsend.send_once('hdmi_switch', ['KEY_3'])

# Screen
if arguments.has_key("screen_state"):
    screen_state = int(arguments["screen_state"].value)

    if screen_state == 0:
        irsend.send_once('screen', ['KEY_0'])
    if screen_state == 1:
        irsend.send_once('screen', ['KEY_2'])

# Projector:
if arguments.has_key("projector_state"):
    projector_state = int(arguments["projector_state"].value)

    if projector_state == 0:
        irsend.send_once('projector', ['KEY_POWER2'])
        time.sleep(1)
        irsend.send_once('projector', ['KEY_POWER2'])
    if projector_state == 1:
        irsend.send_once('projector', ['KEY_POWER'])

print 'Content-Type: application/json;charset=UTF-8\n\n{"success":true}'