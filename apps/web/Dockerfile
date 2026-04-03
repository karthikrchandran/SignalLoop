# Stage 0, "build-stage", based on Bun, to build and compile the frontend
FROM oven/bun:1 AS build-stage

WORKDIR /app

COPY package.json bun.lock /app/

COPY apps/web/package.json /app/apps/web/

WORKDIR /app/apps/web

RUN bun install

COPY ./apps/web /app/apps/web
ARG VITE_API_URL

RUN bun run build


# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1

COPY --from=build-stage /app/apps/web/dist/ /usr/share/nginx/html

COPY ./apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY ./apps/web/nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
