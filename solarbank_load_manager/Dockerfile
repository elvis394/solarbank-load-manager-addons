ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip

COPY rootfs /

RUN mkdir -p /app/frontend/dist/assets \
    && cp /app/frontend/src/index.html /app/frontend/dist/index.html \
    && cp /app/frontend/src/main.js /app/frontend/dist/assets/main.js \
    && cp /app/frontend/src/styles.css /app/frontend/dist/assets/styles.css \
    && chmod +x /etc/services.d/solarbank-manager/run

WORKDIR /app/backend
RUN apk add --no-cache --virtual .build-deps build-base \
    && pip install --break-system-packages --no-cache-dir -r requirements.txt \
    && apk del .build-deps

EXPOSE 8099
