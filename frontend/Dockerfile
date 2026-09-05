FROM node:22-slim AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Vite only reads VITE_* variables at build time, baking them into the
# static JS — there's no "runtime env var" for a static bundle. Passed as
# a build ARG so it works the same via `docker build --build-arg` locally,
# docker-compose (build.args), or a platform's own build-arg mechanism.
# Left unset, api-client.ts falls back to a relative /api/v1 path, which
# only works when something in front of this container (nginx, in the
# docker-compose topology) proxies it to a backend on the same network —
# a split-host deployment (frontend and backend as separate services on
# different domains) must set this to the backend's real public origin.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html

# A template, not a static conf: nginx's own official entrypoint runs
# envsubst on every *.template file here into /etc/nginx/conf.d/ at
# container start, substituting $PORT — needed because most PaaS hosts
# (Railway included) inject a dynamic PORT and expect the container to
# bind to it; a static "listen 80" (the old approach, correct only for
# docker-compose's fixed internal network) would ignore that entirely.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Default for plain `docker run`/docker-compose, where nothing else sets
# PORT — envsubst has no concept of a fallback value, so this must always
# be defined. Railway overrides it with its own injected value.
ENV PORT=80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD sh -c 'wget -qO- http://127.0.0.1:${PORT}/ || exit 1'
