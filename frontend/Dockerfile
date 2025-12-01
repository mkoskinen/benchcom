# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Cache-bust arg to force rebuild when needed
ARG CACHEBUST=1

COPY package.json package-lock.json* ./
RUN npm ci --silent 2>/dev/null || npm install

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
