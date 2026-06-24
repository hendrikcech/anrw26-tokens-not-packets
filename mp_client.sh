#!/usr/bin/env bash


parse() {
HELP="(cat <<EOF
--sp    Singlepath mode instead of multipath
--dry   Print the quicheperf command that would be executed
--      Pass following arguments to quicheperf
EOF)"

    ADDR_MODE='mp'
    QUICHEPERF_ARGS=''
    DRY='false'
    MODE='perf'
    while [[ $# -gt 0 ]]; do
    case $1 in
        --sp) ADDR_MODE='sp'; shift ;;
        --dry) DRY='true'; shift ;;
        -h|--help) echo "$HELP"; exit 0 ;;
        --) shift; QUICHEPERF_ARGS="$@"; break ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    done

    LOCAL_ADDRS='-l 10.0.1.1:8000 -l 10.0.2.1:8000'
    REMOTE_ADDRS='-c 10.0.1.2:8000 -c 10.0.2.2:8000'
}

cmd_perf() {
    MP='true'
    if [ "$ADDR_MODE" = "sp" ]; then
        MP='false'
    fi
    cat <<EOF
stdbuf --output=L \
quicheperf client \
$LOCAL_ADDRS \
$REMOTE_ADDRS \
--mp="$MP" \
--logfile="$STDERRDIR/$(date +%y%m%dT%H%M%S)-client.log" \
$QUICHEPERF_ARGS
EOF
        # tee "$STDERRDIR/$(date +%y%m%dT%H%M%S)-client-stdout.log"
}

execute() {
    local cmd="$1"
    if [ "$DRY" = 'true' ]; then
        echo "$cmd"
    else
        eval exec "$cmd"
    fi
}

main() {
    BASE="$(dirname "$0")"
    . "$BASE/common.sh"

    parse "$@"

    env > client_env.log

    if [ "$MODE" = 'perf' ]; then
        execute "$(cmd_perf)"
    else
        echo "Unknown mode '$MODE'"
        exit 1
    fi
}

main "$@"
