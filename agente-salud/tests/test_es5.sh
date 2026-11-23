#!/bin/sh
# Comprueba que el JS del iPad use solo sintaxis ES5 (Safari 9 / iOS 9).
cd "$(dirname "$0")/.." && npx --yes acorn@8 --ecma5 --silent static/ipad.js
