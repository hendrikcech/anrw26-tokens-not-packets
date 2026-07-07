ANRW'26: Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface
---

This repository contains supporting material to the ANRW'26 publication "Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface"

Please cite:
TODO: bibtex

# Overview
- quiche and quicheperf, the application using quiche, are included as git submodules
- [explain the purpose of nix here: especially freezes dependencies, reproducable on other linux systems]
- can also be used without nix if dependencies are installed locally [insert non-exhaustive list: go-task, python3, mininet, rust toolchain for quiche(perf)]

# Guide
## Listing and executing tasks
- [explain that available commands are listed in Taskfile.yml]
- can be listed with `nix develop -c task` [add output of that here for reference]

## Running measurements
- run both stream completion time (SCT) and acknowledgement experiments with `nix develop -c task measure`

## Plotting results
- after the experim


## Notes [ignore this section]
- clone and compile quiche and quicheperf with nix

- `nix develop -i -k HOME -k TERM -c task sct`

- `nix develop -i -c bash --norc --noprofile`

- using sudo: `/usr/bin/sudo -E env "PATH=$PATH" python3 mp_topo.py`

- `rm -rf results/sct; /usr/bin/sudo -E env "PATH=$PATH" python3 mn_runner.py 'root' 'sct' --reps 1`
