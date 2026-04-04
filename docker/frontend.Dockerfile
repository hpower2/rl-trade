FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
COPY apps/frontend/package.json /app/apps/frontend/package.json

RUN npm install

COPY apps/frontend /app/apps/frontend

WORKDIR /app/apps/frontend

RUN npm run build

EXPOSE 4173

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173", "--strictPort"]
