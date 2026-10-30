#!/usr/bin/env python3
from pathlib import Path
import sys

TARGET = Path("sing-box.sh")
if not TARGET.is_file():
    raise SystemExit("ERROR: sing-box.sh not found in current directory")
src = TARGET.read_text(encoding="utf-8")
original = src

# The sync workflow keeps our local patch commit across upstream merges.
# Treat a fully patched file as success so daily/manual workflow runs are repeatable.
if '23_${NODE_TAG[12]}_inbounds.json' in src:
    required = [
        '"Snell")', '"snell")', 'INSTALL_PROTOCOLS=(b c d e f g h i j k l m n)',
        'PORT_SNELL', 'SNELL_PSK', 'CLASH_SNELL', 'version: 5',
        'CLASH2_PORT=', 'obfs_mode'
    ]
    missing = [item for item in required if item not in src]
    if missing:
        raise SystemExit("ERROR: partial Snell patch detected; missing: " + ", ".join(missing))
    print("Snell v5 patch already present; nothing to do.")
    raise SystemExit(0)

def replace_once(old, new, label):
    global src
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label}: expected 1 anchor, found {count}; no file written.")
    src = src.replace(old, new, 1)

replace_once(
    'PROTOCOL_LIST=("XTLS + reality" "hysteria2" "tuic" "ShadowTLS" "shadowsocks" "trojan" "vmess + ws" "vless + ws + tls" "H2 + reality" "gRPC + reality" "AnyTLS" "naive")',
    'PROTOCOL_LIST=("XTLS + reality" "hysteria2" "tuic" "ShadowTLS" "shadowsocks" "trojan" "vmess + ws" "vless + ws + tls" "H2 + reality" "gRPC + reality" "AnyTLS" "naive" "Snell")',
    "protocol display list")
replace_once(
    'NODE_TAG=("xtls-reality" "hysteria2" "tuic" "ShadowTLS" "shadowsocks" "trojan" "vmess-ws" "vless-ws-tls" "h2-reality" "grpc-reality" "anytls" "naive")',
    'NODE_TAG=("xtls-reality" "hysteria2" "tuic" "ShadowTLS" "shadowsocks" "trojan" "vmess-ws" "vless-ws-tls" "h2-reality" "grpc-reality" "anytls" "naive" "snell")',
    "protocol tag list")
replace_once('INSTALL_PROTOCOLS=(b c d e f g h i j k l m)',
             'INSTALL_PROTOCOLS=(b c d e f g h i j k l m n)',
             "all-protocol preview list")
replace_once('PORT_ANYTLS PORT_NAIVE SELF_SIGNED_FINGERPRINT_SHA256',
             'PORT_ANYTLS PORT_NAIVE PORT_SNELL SNELL_PSK SNELL_OBFS_MODE SELF_SIGNED_FINGERPRINT_SHA256',
             "node-value reset list")

# Add persisted Snell values immediately after the existing Naive reader.
needle = next((x for x in src.splitlines(keepends=True)
               if x.startswith('  [ -s ${WORK_DIR}/conf/*_${NODE_TAG[11]}_inbounds.json ]')), None)
if needle is None or needle.count('NODE_NAME[22]') != 1:
    raise SystemExit("ERROR: Naive node-value anchor not found uniquely; no file written.")
snell_reader = r'''
  # Read Snell v5 settings
  [ -s ${WORK_DIR}/conf/*_${NODE_TAG[12]}_inbounds.json ] && local JSON=$(cat ${WORK_DIR}/conf/*_${NODE_TAG[12]}_inbounds.json) && NODE_NAME[23]=$(sed -n "s/.*\"tag\":\"\(.*\) ${NODE_TAG[12]}.*/\1/p" <<< "$JSON") && PORT_SNELL=$(sed -n 's/.*"listen_port":[[:space:]]*\([0-9]\+\).*/\1/p' <<< "$JSON") && SNELL_PSK=$(awk -F '"' '/"psk"/{print $4; exit}' <<< "$JSON") && SNELL_OBFS_MODE=$(awk -F '"' '/"obfs_mode"/{print $4; exit}' <<< "$JSON")
'''
replace_once(needle, needle + snell_reader, "Snell node-value reader")

# Append the Snell inbound after the Naive inbound block.
naive_end = r'''  # 生成 naive 配置
  CHECK_PROTOCOLS=$(asc "$CHECK_PROTOCOLS" ++)
  if [[ "${INSTALL_PROTOCOLS[@]}" =~ "$CHECK_PROTOCOLS" ]]; then
    [ -z "$PORT_NAIVE" ] && PORT_NAIVE=$[START_PORT+$(awk -v target=$CHECK_PROTOCOLS '{ for(i=1; i<=NF; i++) if($i == target) { print i-1; break } }' <<< "${INSTALL_PROTOCOLS[*]}")]
    NODE_NAME[22]=${NODE_NAME[22]:-"$NODE_NAME_CONFIRM"} && UUID[22]=${UUID[22]:-"$UUID_CONFIRM"}

    cat > ${WORK_DIR}/conf/22_${NODE_TAG[11]}_inbounds.json << EOF
{
    "inbounds":[
        {
            "type":"naive",
            "tag":"${NODE_NAME[22]} ${NODE_TAG[11]}",
            "listen":"::",
            "listen_port":$PORT_NAIVE,
            "users":[
                {
                    "username":"${UUID[22]}",
                    "password":"${UUID[22]}"
                }
            ],
            "tls":{
                "enabled":true,
                "certificate_path":"${WORK_DIR}/cert/cert_200.pem",
                "key_path":"${WORK_DIR}/cert/private.key"
            }
        }
    ]
}
EOF
  fi
}'''
snell_generation = r'''  # Generate Snell v5 inbound (protocol n; node index 23).
  CHECK_PROTOCOLS=$(asc "$CHECK_PROTOCOLS" ++)
  if [[ "${INSTALL_PROTOCOLS[@]}" =~ "$CHECK_PROTOCOLS" ]]; then
    local SNELL_VERSION
    SNELL_VERSION=$("$DIR/sing-box" version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)
    if [[ -z "$SNELL_VERSION" ]] || [[ "$(printf '%s\n' 1.14.0 "$SNELL_VERSION" | sort -V | head -n1)" != "1.14.0" ]]; then
      error "Snell inbound requires sing-box 1.14.0 or newer; detected: ${SNELL_VERSION:-unknown}"
    fi

    [ -z "$PORT_SNELL" ] && PORT_SNELL=$((START_PORT + $(awk -v target="$CHECK_PROTOCOLS" '{ for(i=1; i<=NF; i++) if($i == target) { print i-1; break } }' <<< "${INSTALL_PROTOCOLS[*]}")))
    NODE_NAME[23]=${NODE_NAME[23]:-"$NODE_NAME_CONFIRM"}
    SNELL_PSK=${SNELL_PSK:-"$(openssl rand -hex 16)"}

    if [ -z "$SNELL_OBFS_MODE" ]; then
      if [[ "$IS_FAST_INSTALL" = 'is_fast_install' || "$NONINTERACTIVE_INSTALL" = 'noninteractive_install' ]]; then
        SNELL_OBFS_MODE=none
      else
        hint "Snell v5 HTTP obfuscation: 1. none (default)  2. http"
        reading "Choose [1/2]: " SNELL_OBFS_CHOICE
        [[ "$SNELL_OBFS_CHOICE" = '2' ]] && SNELL_OBFS_MODE=http || SNELL_OBFS_MODE=none
      fi
    fi

    cat > ${WORK_DIR}/conf/23_${NODE_TAG[12]}_inbounds.json << EOF
{
    "inbounds":[
        {
            "type":"snell",
            "tag":"${NODE_NAME[23]} ${NODE_TAG[12]}",
            "listen":"::",
            "listen_port":$PORT_SNELL,
            "version":5,
            "psk":"${SNELL_PSK}",
            "obfs_mode":"${SNELL_OBFS_MODE}"
        }
    ]
}
EOF
  fi
}'''
replace_once(naive_end, naive_end[:-1] + snell_generation, "Snell inbound generator")

# sb -r: allocate the new Snell port after the Naive port.
naive_port = r'''  # 获取 naive 端口
  CHECK_PROTOCOLS=$(asc "$CHECK_PROTOCOLS" ++)
  if [[ "${INSTALL_PROTOCOLS[@]}" =~ "$CHECK_PROTOCOLS" ]]; then
    POSITION=$(awk -v target=$CHECK_PROTOCOLS '{ for(i=1; i<=NF; i++) if($i == target) { print i-1; break } }' <<< "${INSTALL_PROTOCOLS[*]}")
    PORT_NAIVE=${REINSTALL_PORTS[POSITION]}
  else
    unset PORT_NAIVE
  fi
'''
snell_port = r'''
  # 获取 Snell v5 端口
  CHECK_PROTOCOLS=$(asc "$CHECK_PROTOCOLS" ++)
  if [[ "${INSTALL_PROTOCOLS[@]}" =~ "$CHECK_PROTOCOLS" ]]; then
    POSITION=$(awk -v target=$CHECK_PROTOCOLS '{ for(i=1; i<=NF; i++) if($i == target) { print i-1; break } }' <<< "${INSTALL_PROTOCOLS[*]}")
    PORT_SNELL=${REINSTALL_PORTS[POSITION]}
  else
    unset PORT_SNELL SNELL_PSK SNELL_OBFS_MODE
  fi
'''
replace_once(naive_port, naive_port + snell_port, "sb -r Snell port assignment")

# Add Mihomo/OpenClash Snell node to the provider subscription.
clash_anchor = '  echo -n "${CLASH_SUBSCRIBE}" | sed -E \'/^[ ]*#|^--/d\' | sed \'/^$/d\' > ${WORK_DIR}/subscribe/proxies'
clash_insert = r'''  # Snell v5 for Mihomo / OpenClash
  if [ -n "$PORT_SNELL" ]; then
    if [ "$SNELL_OBFS_MODE" = 'http' ]; then
      local CLASH_SNELL="- {name: \"${NODE_NAME[23]} ${NODE_TAG[12]}\", type: snell, server: ${SERVER_IP}, port: ${PORT_SNELL}, psk: \"${SNELL_PSK}\", version: 5, udp: true, obfs-opts: {mode: http, host: bing.com}}"
    else
      local CLASH_SNELL="- {name: \"${NODE_NAME[23]} ${NODE_TAG[12]}\", type: snell, server: ${SERVER_IP}, port: ${PORT_SNELL}, psk: \"${SNELL_PSK}\", version: 5, udp: true}"
    fi
    local CLASH_SUBSCRIBE+="
  $CLASH_SNELL
"
  fi

'''
replace_once(clash_anchor, clash_insert + clash_anchor, "Mihomo Snell proxy entry")

# Include Snell in Clash2's parallel proxy and group arrays.
replace_once(
    'CLASH2_PORT=("$PORT_XTLS_REALITY" "$PORT_HYSTERIA2" "$PORT_TUIC" "$PORT_SHADOWTLS" "$PORT_SHADOWSOCKS" "$PORT_TROJAN" "$PORT_VMESS_WS" "$PORT_VLESS_WS" "$PORT_GRPC_REALITY" "$PORT_ANYTLS")',
    'CLASH2_PORT=("$PORT_XTLS_REALITY" "$PORT_HYSTERIA2" "$PORT_TUIC" "$PORT_SHADOWTLS" "$PORT_SHADOWSOCKS" "$PORT_TROJAN" "$PORT_VMESS_WS" "$PORT_VLESS_WS" "$PORT_GRPC_REALITY" "$PORT_ANYTLS" "$PORT_SNELL")',
    "Clash2 port array")
replace_once(
    'CLASH2_PROXY_INSERT=("$CLASH_XTLS_REALITY" "$CLASH_HYSTERIA2" "$CLASH_TUIC" "$CLASH_SHADOWTLS" "$CLASH_SHADOWSOCKS" "$CLASH_TROJAN" "$CLASH_VMESS_WS" "$CLASH_VLESS_WS" "$CLASH_GRPC_REALITY" "$CLASH_ANYTLS")',
    'CLASH2_PROXY_INSERT=("$CLASH_XTLS_REALITY" "$CLASH_HYSTERIA2" "$CLASH_TUIC" "$CLASH_SHADOWTLS" "$CLASH_SHADOWSOCKS" "$CLASH_TROJAN" "$CLASH_VMESS_WS" "$CLASH_VLESS_WS" "$CLASH_GRPC_REALITY" "$CLASH_ANYTLS" "$CLASH_SNELL")',
    "Clash2 proxy array")
replace_once(
    '"- ${NODE_NAME[21]} ${NODE_TAG[10]}")',
    '"- ${NODE_NAME[21]} ${NODE_TAG[10]}" "- ${NODE_NAME[23]} ${NODE_TAG[12]}")',
    "Clash2 proxy group array")

if src == original:
    raise SystemExit("ERROR: no changes made.")
if '23_${NODE_TAG[12]}_inbounds.json' not in src or 'type: snell' not in src or '"version":5' not in src:
    raise SystemExit("ERROR: post-patch feature checks failed; no file written.")

TARGET.write_text(src, encoding="utf-8")
print("Snell v5 patch applied to sing-box.sh")
print("Added protocol n, Snell v5 inbound, persisted PSK/obfs, sb -r management, and Mihomo/OpenClash subscriptions.")
