FROM adguard/adguardhome:v0.107.79
# Upstream file capabilities conflict with cap_drop ALL on this QNAP kernel.
# DNS uses 1053 inside the container, so it needs no privileged-port capability.
RUN cat /opt/adguardhome/AdGuardHome > /opt/adguardhome/AdGuardHome.nonroot \
    && chmod 0555 /opt/adguardhome/AdGuardHome.nonroot \
    && mv /opt/adguardhome/AdGuardHome.nonroot /opt/adguardhome/AdGuardHome
