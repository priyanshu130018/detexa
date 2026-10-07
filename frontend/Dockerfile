# ── Multi-stage Build for Detexa React + TypeScript Frontend ─────────────────
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Build Vite production bundle
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

EXPOSE 5173

# Serve production preview without Nginx
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
