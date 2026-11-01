# Node test runner image. Build: make runtimes (tag: assess-node20).
# backend/runner starts one locked-down container per run: no network, read-only root,
# writable /workspace only, uid 10001.
FROM node:20.20.2-slim

ENV NODE_ENV=test \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

# Jest and its dependencies, installed from a lockfile, so tests run with no network.
# On PATH for every user; NODE_PATH lets tests require e.g. @jest/globals.
COPY jest/package.json jest/package-lock.json /opt/jest/
RUN cd /opt/jest && npm ci --omit=dev && npm cache clean --force
ENV PATH=/opt/jest/node_modules/.bin:$PATH \
    NODE_PATH=/opt/jest/node_modules \
    NPM_CONFIG_OFFLINE=true

RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin runner \
    && mkdir /workspace \
    && chown runner:runner /workspace

USER 10001
WORKDIR /workspace
