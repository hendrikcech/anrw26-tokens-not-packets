#!/usr/bin/env bash

set -eu

parse() {
HELP="(cat <<EOF
--dry    Print the quicheperf command
--proxy  Run in proxy instead of perf mode
--nto1   Use if using mininet nto1 type
-h|--help   Print this help message
--      Pass following arguments to quicheperf
EOF)"

    QUICHEPERF_ARGS=''
    DRY='false'
    MININET='nton'
    MODE='perf'
    while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry) DRY='true'; shift ;;
        --proxy) MODE='proxy'; shift ;;
        --nto1) MININET='nto1'; shift ;;
        -h|--help) echo "$HELP"; exit 0 ;;
        --) shift; QUICHEPERF_ARGS="$@"; break ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    done

    if [ "$MININET" = "nton" ]; then
        LOCAL_ADDRS='-l 10.0.1.2:8000 -l 10.0.2.2:8000'
    elif [ "$MININET" = "nto1" ]; then
        LOCAL_ADDRS='-l 10.0.1.2:8000'
    else
        echo "Unknown mode"
        exit 1
    fi
}

cmd_perf() {
    cat <<EOF
stdbuf --output=L \
$QUICHEPERF_EXE server \
--cert "$CERT" --key "$KEY" \
--mp true \
--logfile="$STDERRDIR/$(date +%y%m%dT%H%M%S)-server.log" \
$LOCAL_ADDRS \
$QUICHEPERF_ARGS
EOF
}

cmd_proxy() {
    cat <<EOF
stdbuf --output=L \
"$QUICHEPERF_EXE" proxy-server \
--cert "$CERT" --key "$KEY" \
--mp true \
--tun mp0 \
--logfile="$STDERRDIR/$(date +%y%m%dT%H%M%S)-server.log" \
$LOCAL_ADDRS \
$QUICHEPERF_ARGS
EOF
}

execute() {
    local cmd="$1"
    if [ "$DRY" = 'true' ]; then
        echo "$cmd"
    else
        echo "$cmd"
        eval exec $cmd
        # eval "$cmd"
    fi
}

main() {
    BASE="$(dirname "$0")"
    . "$BASE/common.sh"

    parse "$@"

    CERT="${BASE}/../quicheperf/src/cert.crt"
    KEY="${BASE}/../quicheperf/src/cert.key"

    if [ -z "${NIX_QUICHEPERF_EXE:-}" ]; then
        cargo build --manifest-path "$QUICHEPERF_TOML" --profile "$CARGO_PROFILE" --bin quicheperf 2>/dev/null
    fi
    # cargo run --manifest-path "$QUICHEPERF_TOML" --bin quicheperf --profile "$CARGO_PROFILE" -- server \

    if [ "$MODE" = 'perf' ]; then
        execute "$(cmd_perf)"
    elif [ "$MODE" = 'proxy' ]; then
        execute "$(cmd_proxy)"
    else
        echo "Unknown mode '$MODE'"
        exit 1
    fi
}

main "$@"
