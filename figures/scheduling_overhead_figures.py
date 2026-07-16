#!/usr/bin/env python3
"""Extracted from timestamp_analysis.ipynb: reproduces scheduling_overhead_minrtt_ecf_cdf.pdf
from the per-call timestamp CSVs.
"""

import argparse
import os
import re
import multiprocessing

import pandas as pd
import matplotlib.pyplot as plt

import utils

END_NAMES = {'send_frame_scheduler', 'send_packet_scheduler'}
LINESTYLES = {'up-front': '-', 'per-packet': '--'}


def parse_timestamps(args):
    path, regex = args

    matches = regex.search(path)
    if matches is None:
        print(f"regex did not match path '{path}'")
        return None

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        print(f"Skipping empty file: {path}")
        return None
    df["side"] = "server" if "server" in os.path.basename(path) else "client"

    for k, v in matches.groupdict().items():
        value = v
        try:
            value = int(v)
        except:
            pass
        df[k] = value

    return df


def assign_iteration(group):
    end_mask = group['name'].isin(END_NAMES)
    return (end_mask.shift(1, fill_value=False).cumsum() + 1).astype(int)


def assign_iterations(df):
    df = df.sort_values(['network', 'scheduler', 'rep', 'side', 'timestamp'])
    df['iteration'] = (
        df.groupby(['network', 'scheduler', 'rep', 'side'], group_keys=False)
        .apply(assign_iteration)
    )

    # Drop the last (incomplete) iteration per group -- it has no closing boundary
    last_iter = df.groupby(['network', 'scheduler', 'rep', 'side'])['iteration'].transform('max')
    return df[df['iteration'] < last_iter]


def compute_scheduling_overhead(df_subset, fscheduler_name, pscheduler_name):
    """Per-packet scheduling overhead for one frame scheduler / packet scheduler pair.

    Frame scheduler: run_frame_schedulers duration / count(get_packet_for_path) per
    iteration, repeated once per get_packet_for_path call.
    Packet scheduler: for each send_single_with_instructions(), take the preceding
    get_best_path() duration.
    """
    fscheduler_df = df_subset[df_subset['scheduler'] == fscheduler_name]

    rfs_dur = (
        fscheduler_df[fscheduler_df['name'] == 'run_frame_schedulers()']
        .groupby(['network', 'scheduler', 'rep', 'side', 'iteration'])['duration']
        .sum()
        .rename('rfs_duration')
    )
    gpp_count = (
        fscheduler_df[fscheduler_df['name'] == 'get_packet_for_path()']
        .groupby(['network', 'scheduler', 'rep', 'side', 'iteration'])
        .size()
        .rename('gpp_count')
    )
    fscheduler_overhead = (
        pd.concat([rfs_dur, gpp_count], axis=1)
        .dropna()
        .assign(overhead=lambda x: x['rfs_duration'] / x['gpp_count'])
        .loc[lambda x: x.index.repeat(x['gpp_count'].astype(int))]
        .reset_index()[['network', 'scheduler', 'rep', 'side', 'overhead']]
    )

    pscheduler_df = df_subset[df_subset['scheduler'] == pscheduler_name]
    relevant = (
        pscheduler_df[pscheduler_df['name'].isin(['get_best_path()', 'send_single_with_instructions()'])]
        .sort_values(['network', 'rep', 'side', 'timestamp'])
    )

    def extract_pscheduler_overhead(group):
        prev_name = group['name'].shift(1)
        prev_dur = group['duration'].shift(1)
        mask = (group['name'] == 'send_single_with_instructions()') & (prev_name == 'get_best_path()')
        result = group[mask].copy()
        result['overhead'] = prev_dur[mask].values
        return result[['scheduler', 'overhead']]

    pscheduler_overhead = (
        relevant.groupby(['network', 'rep', 'side'], group_keys=True)
        .apply(extract_pscheduler_overhead, include_groups=False)
        .reset_index()[['network', 'scheduler', 'rep', 'side', 'overhead']]
    )

    return pd.concat([fscheduler_overhead, pscheduler_overhead], ignore_index=True)


def overhead_data(df, fscheduler_name, pscheduler_name):
    df_subset = df[df['scheduler'].isin([fscheduler_name, pscheduler_name])]
    scheduling_overhead = compute_scheduling_overhead(df_subset, fscheduler_name, pscheduler_name)

    overhead_us = scheduling_overhead.copy()
    overhead_us['overhead_us'] = overhead_us['overhead'].dt.total_seconds() * 1e6

    schedulers = [fscheduler_name, pscheduler_name]
    labels = ['up-front', 'per-packet']
    return [overhead_us[overhead_us['scheduler'] == s]['overhead_us'] for s in schedulers], labels


def plot_minrtt_ecf_cdf(df):
    data_minrtt, labels = overhead_data(df, 'fscheduler-minrtt', 'pscheduler-minrtt')
    data_ecf, _ = overhead_data(df, 'fscheduler-ecf', 'pscheduler-ecf')

    fig_dimensions = (2.2, 1.3)
    fig, (ax_minrtt, ax_ecf) = plt.subplots(1, 2, figsize=(fig_dimensions[0] * 2, fig_dimensions[1]))

    for label, d in zip(labels, data_minrtt):
        utils.plot_cdf(ax_minrtt, d, label=label, color='black', linestyle=LINESTYLES[label])
    ax_minrtt.set_xlabel('MinRTT: Runtime / Packet [µs]')
    ax_minrtt.set_ylabel('CDF')
    ax_minrtt.set_xlim((-10, 1300))

    for label, d in zip(labels, data_ecf):
        utils.plot_cdf(ax_ecf, d, label=label, color='black', linestyle=LINESTYLES[label])
    ax_ecf.set_xlabel('ECF: Runtime / Packet [µs]')
    ax_ecf.set_xlim((-10, 1300))
    ax_ecf.legend()

    return fig


def main():
    parser = argparse.ArgumentParser(description="Parse per-call timestamp CSVs to compute scheduling overhead")
    parser.add_argument("csvs", nargs="+", help="The per-call timestamp CSV files")
    parser.add_argument("--regex", required=True, help="Metadata regex with named groups (network, scheduler, rep)")
    parser.add_argument("--hide-ylabel", action="store_true")
    parser.add_argument("-o")
    args = parser.parse_args()

    regex = re.compile(args.regex)

    map_args = [(csv, regex) for csv in args.csvs]

    multiprocessing.set_start_method("spawn")
    df = utils.parse(parse_timestamps, map_args, parallel=True)
    if df is None:
        return

    df["duration"] = pd.to_timedelta(df["duration"], unit="ns")
    df = assign_iterations(df)

    utils.set_plt_style(8)

    fig = plot_minrtt_ecf_cdf(df)

    if args.hide_ylabel:
        fig.get_axes()[0].set_ylabel("")

    if args.o:
        fig.savefig(args.o, bbox_inches="tight", pad_inches=0)
    else:
        plt.show()


if __name__ == "__main__":
    main()
