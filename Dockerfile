FROM python:3.12-alpine

RUN apk add --no-cache caddy

WORKDIR /app
COPY api /app/api

COPY Caddyfile /etc/caddy/Caddyfile
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

COPY *.html /srv/
COPY en /srv/en/
COPY assets /srv/assets/
COPY sitemap.xml robots.txt /srv/

EXPOSE 8080
CMD ["/start.sh"]
