FROM node:24.18.0-alpine

ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV LANG=C.UTF-8
WORKDIR /opt/app

RUN apk add --no-cache bash jq

COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./
RUN if node -e "const p=require('./package.json'); process.exit(p.scripts && p.scripts.build ? 0 : 1)"; then npm run build; fi
RUN npm prune --omit=dev && npm cache clean --force

COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 3000

CMD ["/run.sh"]
