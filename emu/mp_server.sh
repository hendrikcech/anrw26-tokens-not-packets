#!/usr/bin/env bash

set -eu

parse() {
HELP="(cat <<EOF
--dry    Print the quicheperf command
--timestamp  Enable send-path timestamp logging (sets TIMESTAMP_LOG)
-h|--help   Print this help message
--      Pass following arguments to quicheperf
EOF)"

    QUICHEPERF_ARGS=''
    DRY='false'
    MODE='perf'
    TIMESTAMP='false'
    while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry) DRY='true'; shift ;;
        --timestamp) TIMESTAMP='true'; shift ;;
        -h|--help) echo "$HELP"; exit 0 ;;
        --) shift; QUICHEPERF_ARGS="$@"; break ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    done

    LOCAL_ADDRS='-l 10.0.1.2:8000 -l 10.0.2.2:8000'
}

cmd_perf() {
    cat <<EOF
stdbuf --output=L \
quicheperf server \
--cert "$CERT" --key "$KEY" \
--mp true \
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
    fi
}

main() {
    BASE="$(dirname "$0")"
    . "$BASE/common.sh"

    parse "$@"

    CERT="${BASE}/cert.crt"
    KEY="${BASE}/cert.key"

    # quicheperf and quiche both enable timestamp logging when TIMESTAMP_LOG is
    # set. quiche writes to this exact path; quicheperf writes to a sibling file
    # with a "quicheperf_" prefix on the basename.
    if [ "$TIMESTAMP" = 'true' ]; then
        export TIMESTAMP_LOG="$STDERRDIR/$(date +%y%m%dT%H%M%S)-server-timestamps.csv"
    fi

    if [ "$MODE" = 'perf' ]; then
        execute "$(cmd_perf)"
    else
        echo "Unknown mode '$MODE'"
        exit 1
    fi
}

main "$@"
