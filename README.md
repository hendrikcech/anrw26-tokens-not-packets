Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface (ANRW'26)
---

This repository contains supporting material to the Applied Networking Research Workshop (ANRW) 2026 publication "Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface".

If you use this repository or dataset in your research, please cite our paper:

<details>
<summary>BibTeX</summary>

```bibtex
@inproceedings{cech2026tokens,
author = {Cech, Hendrik and Bokelmann, Patrick and Mohan, Nitinder},
title = {Tokens, Not Packets: Rethinking the Multipath QUIC Scheduling Interface},
year = {2026},
isbn = {9798400728761},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3822163.3827925},
doi = {10.1145/3822163.3827925},
abstract = {The Multipath QUIC extension has enabled a growing class of stream-aware schedulers that exploit QUIC's multiplexed streams, mixed reliable and unreliable delivery, and explicit control frames. Progress on these ideas is bottlenecked by an interface inherited from Multipath TCP, in which the scheduler is a function called during packet generation to pick a path. This coupling yields invasive, library-specific scheduler implementations, hinders application-steered scheduling, and makes fair cross-scheduler comparison impractical. We present an up-front, token-based MPQUIC scheduling interface designed primarily for research use, guided by three design choices: unified up-front decisions that address path selection, stream assignment, and duplication jointly; inspectability of scheduling policy as persistent data structures; and mechanism safety through a boundary that preserves protocol invariants. The scheduler reads transport state through a mediating ConnState object and writes policy into per-path, multi-level queues of abstract tokens that the library drains into packets. We prototype the interface in Cloudflare's quiche, reproduce published scheduler behavior, and demonstrate a new degree of freedom—explicit control frame routing—that reduces median stream completion time by 138 ms in our evaluation.},
booktitle = {Proceedings of the 2026 Applied Networking Research Workshop},
pages = {140–146},
numpages = {7},
keywords = {MPQUIC, multipath, QUIC, scheduling, scheduler},
location = {Hilton Park, Vienna, Austria},
series = {ANRW '26}
}
```

</details>

# Overview

We implemented our scheduling model in quiche, building on the [Multipath QUIC fork](https://github.com/qdeconinck/quiche/tree/multipath) by Quentin De Coninck. Our quiche modifications live at [hendrikcech/quiche](https://github.com/hendrikcech/quiche/tree/frame-scheduler) on the `frame-scheduler` branch. On top of quiche we developed [quicheperf](https://github.com/hendrikcech/quicheperf), an application that uses quiche as a library and drives our scheduler implementations during evaluation.

This repository holds the automation around those two components. It contains the scripts to run evaluations in a Mininet-based emulation environment and the scripts that produced the figures in the paper. The data plotted in the paper is included as well, under `results/`. Everything is wrapped as tasks for [Task](https://taskfile.dev) (the `go-task` runner), defined in `Taskfile.yml`.

The only dependency you need to install yourself is [Nix](https://nixos.org). The `flake.nix` pins every other dependency (quicheperf and its quiche build, Python and its packages, Mininet, Open vSwitch, and `go-task`) to exact versions through `flake.lock`, so an evaluation runs the same way on any Linux system without polluting the host with globally installed packages. Entering the development shell also bootstraps the Open vSwitch daemons that Mininet needs.

If you prefer not to use Nix, the repository still works as long as the dependencies are available on your system. You will at least need `go-task`, `python3` with the packages listed in `requirements.txt`, Mininet with Open vSwitch, and a Rust toolchain to build quiche and quicheperf. In that case, drop the `nix develop -c` prefix from the commands below and run the tasks directly.

# Guide

## Listing and executing tasks

All available commands are defined in `Taskfile.yml` and can be listed with `nix develop -c task`:

```
* measure-all:                        Run all quicheperf measurements
* measure-scheduler-timestamps:       Run the stream (sct) and packet (pkt) scheduler experiments with timestamp logging enabled
* plot-ack-emu:                       Plot the data of your own emulation run from `task mn-run:ack`
* plot-ack-paper:                     Plot Figure 4 (b) with the data shown in the paper.
* plot-all:                           Plot all paper figures
* plot-sct-emu:                       Plot the data of your own emulation run from `task mn-run:sct`
* plot-sct-paper:                     Plot Figure 4 (a) with the data shown in the paper.
* plot-so-paper:                      Plot Figure 3 with the data shown in the paper.
* plot-timestamp-emu:                 Plot the timestamp overhead of your own emulation run from `task mn-run:timestamp`
* mn-run-timestamp:*:                 Run a specific experiment with mn_runner.py and timestamp logging enabled; deletes previous experiment results
* mn-run:*:                           Run a specific experiment with mn_runner.py; deletes previous experiment results
```

Run any of them with `nix develop -c task <name>`. The first invocation takes a while because Nix pulls quicheperf and builds it against our quiche fork; subsequent runs reuse the cached build.

## Reproducing the paper figures

To regenerate every figure from the data shipped in `results/`, run `nix develop -c task plot-all`. This produces `results/sct.pdf` (Figure 4a), `results/ack.pdf` (Figure 4b), and `results/so.pdf` (Figure 3). The individual `plot-*-paper` tasks generate them one at a time.

## Running your own measurements

Run both the stream completion time (SCT) and acknowledgement experiments with `nix develop -c task measure-all`. Under the hood this calls the parameterized `mn-run:sct` and `mn-run:ack` tasks, which invoke `emu/mn_runner.py` inside Mininet for 30 repetitions each and write their output under `results/sct/` and `results/ack/`. Because these tasks first delete any previous results for the experiment, they prompt for confirmation before starting.

Nix takes care of building the software under test: entering the development shell pulls quicheperf from its flake and compiles it together with our quiche fork, so no manual build step is required. If you want to inspect or run the resulting binary directly, ask Nix for its path with `nix develop -c which quicheperf`, or invoke it straight away with `nix develop -c quicheperf --help`.

To measure scheduling overhead, run `nix develop -c task measure-scheduler-timestamps`. This repeats the stream and packet scheduler experiments with per-decision timestamp logging enabled and stores the results under `results/timestamp/`.

## Plotting your own results

Once you have run your own measurements, plot them with the `-emu` tasks: `nix develop -c task plot-sct-emu`, `plot-ack-emu`, and `plot-timestamp-emu`. Each reads the data your measurement run wrote under `results/` and, if that data is missing, tells you which measurement task to run first. The resulting PDFs are written back into `results/`.
