# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json /app/
COPY apps/frontend/package.json /app/apps/frontend/package.json

RUN --mount=type=cache,target=/root/.npm \
    npm ci --cache /root/.npm

COPY apps/frontend /app/apps/frontend

WORKDIR /app/apps/frontend

RUN npm run build

FROM nginx:1.27-alpine

COPY docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/frontend/dist /usr/share/nginx/html

EXPOSE 80
