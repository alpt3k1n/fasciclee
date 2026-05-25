FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci --prefer-offline
COPY . .
RUN npm run build

FROM scratch
COPY --from=builder /app/dist /dist
