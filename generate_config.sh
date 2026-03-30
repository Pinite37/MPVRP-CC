#!/bin/bash
source .env
sed "s|__API_URL__|$API_URL|g" \
  pages/static/js/config.template.js > pages/static/js/config.js
echo "config.js généré avec API_URL=$API_URL"