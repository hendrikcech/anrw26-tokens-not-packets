ANRW'26: Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface
---

This repository contains supporting material to the ANRW'26 publication "Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface"

Please cite:
TODO: bibtex

# Guide
## Running measurements
- clone and compile quiche and quicheperf with nix

- `nix develop -i -k HOME -k TERM -c task sct`

- `nix develop -i -c bash --norc --noprofile`
