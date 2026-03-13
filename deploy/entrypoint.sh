#!/bin/sh
# Substitute NOVAPAW_PORT in supervisord template and start supervisord.
# Default port 8088; override at runtime with -e NOVAPAW_PORT=3000.
set -e
export NOVAPAW_PORT="${NOVAPAW_PORT:-8088}"
envsubst '${NOVAPAW_PORT}' \
  < /etc/supervisor/conf.d/supervisord.conf.template \
  > /etc/supervisor/conf.d/supervisord.conf
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
