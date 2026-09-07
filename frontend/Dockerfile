# hn.fm frontend — Nuxt 4 built as a Nitro node server.
#
# `nuxt build` (not `nuxt generate`) on purpose: the node server reads
# NUXT_PUBLIC_API_BASE at start, so one image serves any hostname. A static
# build would bake the API base in at build time.
#
# Built natively on the amd64 Forgejo runner; better-sqlite3 (pulled in by
# @nuxt/content) compiles for the arch it runs on, so no cross-build here.
FROM node:22-bookworm-slim AS build
WORKDIR /app
# Native module toolchain for better-sqlite3 when no prebuilt binary matches.
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY . .
RUN yarn build

FROM node:22-bookworm-slim
ENV NODE_ENV=production \
    NITRO_HOST=0.0.0.0 \
    NITRO_PORT=3000 \
    NUXT_PUBLIC_API_BASE=http://localhost:8000
WORKDIR /app
COPY --from=build /app/.output ./.output
# @nuxt/content keeps its SQLite store under .data; give the non-root user a
# writable spot for it.
RUN mkdir -p /app/.data && chown -R node:node /app
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
