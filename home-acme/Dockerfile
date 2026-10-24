FROM docker.io/goacme/lego:v5.5.2@sha256:1944e8c36055beec47c7de6f15202b41128be75eea0ffa257f0c14d93c5155fd AS lego
FROM docker.io/library/python:3.14-alpine@sha256:601e99e090cb08c2784a42395487709500bc39930307fe72f3f11a8f3c430762
ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
RUN apk add --no-cache ca-certificates openssl
COPY --from=lego /lego /usr/local/bin/lego
COPY app/run.py /usr/local/bin/home-acme.py
RUN python3 -m py_compile /usr/local/bin/home-acme.py && lego run --help >/dev/null
CMD ["python3", "-u", "/usr/local/bin/home-acme.py"]
