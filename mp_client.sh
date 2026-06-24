#!/usr/bin/env bash


parse() {
HELP="(cat <<EOF
--sp    Singlepath mode instead of multipath
--nto1  nto1 mode
--proxy  Run in proxy instead of perf mode
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
        --nto1) ADDR_MODE='nto1'; shift ;;
        --proxy) MODE='proxy'; shift ;;
        --dry) DRY='true'; shift ;;
        -h|--help) echo "$HELP"; exit 0 ;;
        --) shift; QUICHEPERF_ARGS="$@"; break ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    done

    if [ "$ADDR_MODE" = "sp" ]; then
        LOCAL_ADDRS='-l 10.0.1.1:8000'
        REMOTE_ADDRS='-c 10.0.1.2:8000'
    elif [ "$ADDR_MODE" = "nto1" ]; then
        LOCAL_ADDRS='-l 10.0.1.1:8000 -l 10.0.2.1:8000'
        REMOTE_ADDRS='-c 10.0.1.2:8000 -c 10.0.1.2:8000'
    elif [ "$ADDR_MODE" = "mp" ]; then
        LOCAL_ADDRS='-l 10.0.1.1:8000 -l 10.0.2.1:8000'
        REMOTE_ADDRS='-c 10.0.1.2:8000 -c 10.0.2.2:8000'
    else
        echo "Invalid argument"
        exit 1
    fi
}

cmd_perf() {
    MP='true'
    if [ "$ADDR_MODE" = "sp" ]; then
        MP='false'
    fi
    cat <<EOF
stdbuf --output=L \
"$QUICHEPERF_EXE" client \
$LOCAL_ADDRS \
$REMOTE_ADDRS \
--mp="$MP" \
--logfile="$STDERRDIR/$(date +%y%m%dT%H%M%S)-client.log" \
$QUICHEPERF_ARGS
EOF
        # tee "$STDERRDIR/$(date +%y%m%dT%H%M%S)-client-stdout.log"
}

cmd_proxy() {
    MP='true'
    if [ "$ADDR_MODE" = "sp" ]; then
        MP='false'
    fi
    cat <<EOF
stdbuf --output=L \
"$QUICHEPERF_EXE" proxy-client \
$LOCAL_ADDRS \
$REMOTE_ADDRS \
--mp="$MP" \
--logfile="$STDERRDIR/$(date +%y%m%dT%H%M%S)-client.log" \
--tun mp0 \
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

    if [ -z "${NIX_QUICHEPERF_EXE:-}" ]; then
        cargo build --manifest-path "$QUICHEPERF_TOML" --profile "$CARGO_PROFILE" --bin quicheperf
    fi

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
