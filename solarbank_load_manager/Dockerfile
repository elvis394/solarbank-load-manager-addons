ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip

COPY rootfs /

RUN mkdir -p /app/frontend/dist/assets \
    && cp /app/frontend/src/index.html /app/frontend/dist/index.html \
    && cp /app/frontend/src/main.js /app/frontend/dist/assets/main.js \
    && cp /app/frontend/src/styles.css /app/frontend/dist/assets/styles.css

WORKDIR /app/backend
RUN pip install --break-system-packages --no-cache-dir -r requirements.txt

EXPOSE 8099
