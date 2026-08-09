FROM node:24-alpine

WORKDIR /app/frontend

COPY package*.json ./
RUN npm ci

COPY . .

ENV VITE_API_BASE_URL=/api

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]