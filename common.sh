#!/usr/bin/env sh

set -eu

# https://stackoverflow.com/a/246128
# The directory of this file
BASE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# -------
# Adapt these values to your requirements
export RUSTUP_HOME=/home/cech/.rustup
export CARGO_HOME=/home/cech/.cargo
export QUICHE_TOML="${BASE}/../quiche/Cargo.toml"
export QUICHEPERF_TOML="${BASE}/../quicheperf/Cargo.toml"

if [ -z "${NIX_QUICHEPERF_EXE:-}" ]; then
    if [ ! -e "$RUSTUP_HOME" ] || [ ! -e "$CARGO_HOME" ] || [ ! -f "$QUICHE_TOML" ] || [ ! -f "$QUICHEPERF_TOML" ]; then
        echo "A custom variable seems to be wrongly defined in ${BASE}/common.sh"
        echo "Adjust the paths to your environment"
        exit 1
    fi
fi
# ---------

export QLOGDIR="${QLOGDIR:-${BASE}/qlog}"
# export SSLKEYLOGFILE="${BASE}/sslkeylog.log"

export RUST_LOG="${RUST_LOG:-trace}"
# export RUST_LOG="${RUST_LOG:-trace,quiche::recovery=debug}"

export STDERRDIR="${STDERRDIR:-${BASE}/stderr}"
# export CARGO_PROFILE='release' # 'dev'
export CARGO_PROFILE="${CARGO_PROFILE:-dev}"
export RUST_BACKTRACE=1

if [ -n "${NIX_QUICHEPERF_EXE:-}" ]; then
    export QUICHEPERF_EXE="$NIX_QUICHEPERF_EXE"
else
    export QUICHEPERF_EXE="$(dirname -- "$QUICHEPERF_TOML")/target/$([ "$CARGO_PROFILE" = "release" ] && echo "release" || echo "debug")/quicheperf"
fi

mkdir -p "$QLOGDIR"
mkdir -p "$STDERRDIR"

_local_ips() {
    ip -j a | jq -r '.[].addr_info[] | select(.family == "inet") | .local | select(. | startswith("10"))'
}

local_ips() {
    (
        IFS=$'\n'
        ips=(_local_ips)
    )
}

# https://stackoverflow.com/a/17841619
join_by() {
  local d=${1-} f=${2-}
  if shift 2; then
    printf %s "$f" "${@/#/$d}"
  fi
}
