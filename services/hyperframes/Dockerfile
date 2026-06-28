# HyperFrames render sidecar — Node + Chromium + ffmpeg + the hyperframes CLI.
# Based on hyperframes' own packages/cli/src/docker/Dockerfile.render (their
# recommended deterministic-render setup) plus a tiny HTTP wrapper so the Python
# pipeline can render a composition over the network. Clean + portable: this is a
# standard image, so it drops straight into k3s later (no host coupling).
FROM node:22-bookworm-slim

ARG HYPERFRAMES_VERSION=latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip ffmpeg chromium \
    libgbm1 libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 \
    libxdamage1 libxrandr2 libcups2 libasound2 libpangocairo-1.0-0 \
    libxshmfence1 libgtk-3-0 \
    fonts-liberation fonts-noto-color-emoji fonts-noto-cjk fonts-noto-core \
    fonts-noto-extra fonts-noto-ui-core fonts-freefont-ttf fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/* && apt-get clean && fc-cache -fv

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CONTAINER=true

RUN npm install -g hyperframes@${HYPERFRAMES_VERSION}

# Use the system (arch-native) chromium. We deliberately do NOT install
# chrome-headless-shell: Google ships it x86-64 only, which fails under Rosetta in
# an arm64 container. System chromium = portable across arm64/amd64.
RUN printf '#!/bin/sh\nexec hyperframes render "$@"\n' > /usr/local/bin/hf-render \
    && chmod +x /usr/local/bin/hf-render

WORKDIR /app
COPY server.mjs /app/server.mjs
EXPOSE 8088
CMD ["node", "/app/server.mjs"]
