#!/bin/sh

[Unit]
Description=flask-server

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/repo/FlaskServer
Environment=NODE_ENV=production
LimitNOFILE=infinity
ExecStart=flaskserver
# ExecStop=/usr/bin/npm run stop
Restart=always
RestartSec=10
KillMode=process

[Install]
WantedBy=default.target
