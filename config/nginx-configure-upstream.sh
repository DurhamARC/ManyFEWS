#!/bin/sh
# vim:sw=4:ts=4:et
# Update variable in default.conf from env

set -e

entrypoint_log() {
    if [ -z "${NGINX_ENTRYPOINT_QUIET_LOGS:-}" ]; then
        echo "$@"
    fi
}

ME=$(basename $0)
DEFAULT_CONF_FILE="etc/nginx/conf.d/default.conf"

if [ ! -f "/$DEFAULT_CONF_FILE" ]; then
    entrypoint_log "$ME: info: /$DEFAULT_CONF_FILE is not a file or does not exist"
    exit 0
fi

if [ -z ${UPSTREAM_SERVER+x} ]; 
then 
    entrypoint_log "$ME: error: Environment Variable \$UPSTREAM_SERVER is unset. Refusing to start";
    exit 1;
fi

entrypoint_log "$ME: info: Setting Upstream Server to ${UPSTREAM_SERVER}:${UPSTREAM_PORT}"

sed -i -e "s/SED_UPSTREAM_SERVER/${UPSTREAM_SERVER}/g" \
       -e "s/SED_UPSTREAM_PORT/${UPSTREAM_PORT}/g" \
       /$DEFAULT_CONF_FILE
exit 0

