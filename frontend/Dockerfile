FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build
RUN chown -R node:node /app

USER node
CMD ["npm", "run", "start"]
