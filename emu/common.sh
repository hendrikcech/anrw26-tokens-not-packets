#!/usr/bin/env sh

set -eu

# https://stackoverflow.com/a/246128
# The directory of this file
BASE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# -------

export QLOGDIR="${QLOGDIR:-${BASE}/qlog}"
# export SSLKEYLOGFILE="${BASE}/sslkeylog.log"

export RUST_LOG="${RUST_LOG:-trace}"
# export RUST_LOG="${RUST_LOG:-trace,quiche::recovery=debug}"

export STDERRDIR="${STDERRDIR:-${BASE}/stderr}"
export RUST_BACKTRACE=1

mkdir -p "$QLOGDIR"
mkdir -p "$STDERRDIR"
