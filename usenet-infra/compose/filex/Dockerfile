FROM ghcr.io/brf-tech/filex:slim-v0.41.4@sha256:cd34a0f0ede3a8470fa908309086438188d543e9c02dce3704814905fbfea2e4 AS trust
# No shell, package manager, executable plugins or obsolete Alpine userland.
FROM scratch
COPY --from=trust /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=trust /usr/share/zoneinfo /usr/share/zoneinfo
# Built from the checksum-pinned source archive and patches/filex/safety.patch.
COPY --chmod=0755 filex /usr/local/bin/filex
WORKDIR /srv/storagebox/Movies
WORKDIR /srv/storagebox/TV
WORKDIR /srv/storagebox/Scratch
WORKDIR /
ENV FILEX_SAFE_TRANSFERS=1 FILEX_TRANSFER_RECEIPTS=/data/transfer-verification HOME=/data
ENTRYPOINT ["/usr/local/bin/filex"]
CMD ["serve"]
