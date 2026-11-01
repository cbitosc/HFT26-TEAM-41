# Headless Chromium for `make e2e`. The image version must match the playwright package.
FROM mcr.microsoft.com/playwright:v1.64.1-noble

WORKDIR /e2e

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

CMD ["node", "demo.mjs"]
