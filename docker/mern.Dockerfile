FROM node:18

WORKDIR /app

COPY templates/mern /app

RUN npm install

EXPOSE 3000

CMD ["node", "app.js"]
