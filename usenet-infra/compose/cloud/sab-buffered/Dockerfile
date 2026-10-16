FROM lscr.io/linuxserver/sabnzbd@sha256:7f173ced3541b46c57c4eb6854765243095c8c8a7563a878044fa0ccfb1f4004
LABEL org.smarthome.sab-buffered="1"
COPY buffered_copy.py install.py verify.py integration_test.py /opt/sab-buffered/
RUN python3 /opt/sab-buffered/install.py && python3 /opt/sab-buffered/verify.py
