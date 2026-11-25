#!/bin/sh
# usage: testbed.sh on|off
# on : park the current etc config as *.yamlx, install the sample config with a fresh token, print the connect command
# off: remove the sample config and restore the parked config
# The sample config is read from this directory; the shng instance itself is started and stopped by hand.
HERE=$(cd "$(dirname "$0")" && pwd)
ETC=${SHNG_ETC:-$(cd "$HERE/../../.." && pwd)/etc}
TOP="plugin.yaml module.yaml logic.yaml logic_groups.yaml admin.yaml"
case "$1" in
on)
  [ -e "$ETC/items/mcp_demo.yaml" ] && { echo "already on"; exit 1; }
  if [ -n "$(find "$ETC" -name '*.yamlx' 2>/dev/null)" ]; then echo "found *.yamlx in $ETC, refusing"; exit 1; fi
  for f in $TOP; do [ -e "$ETC/$f" ] && mv "$ETC/$f" "$ETC/${f}x"; done
  for f in "$ETC"/items/*.yaml; do [ -e "$f" ] && mv "$f" "${f}x"; done
  TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  CLIENT_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  sed -e "s/__TOKEN__/$TOKEN/" -e "s/__CLIENT_TOKEN__/$CLIENT_TOKEN/" "$HERE/plugin.yaml" > "$ETC/plugin.yaml"
  chmod 600 "$ETC/plugin.yaml"
  cp "$HERE/module.yaml" "$HERE/logic.yaml" "$ETC/"
  cp "$HERE/items/mcp_demo.yaml" "$ETC/items/"
  cp "$HERE/logics/mcp_ticker.py" "$ETC/logics/"
  echo "sample config installed in $ETC; start shng, then connect with:"
  echo "claude mcp add --transport http shng-demo http://127.0.0.1:8765/mcp --header \"Authorization: Bearer $TOKEN\""
  echo "second client 'desktop' (read-only), token: $CLIENT_TOKEN" ;;
off)
  rm -f "$ETC/plugin.yaml" "$ETC/module.yaml" "$ETC/logic.yaml" "$ETC/items/mcp_demo.yaml" "$ETC/logics/mcp_ticker.py"
  for f in $TOP; do [ -e "$ETC/${f}x" ] && mv "$ETC/${f}x" "$ETC/$f"; done
  for f in "$ETC"/items/*.yamlx; do [ -e "$f" ] && mv "$f" "${f%x}"; done
  echo "original config restored; remove the MCP entry with: claude mcp remove shng-demo" ;;
*) echo "usage: $0 on|off"; exit 2 ;;
esac
