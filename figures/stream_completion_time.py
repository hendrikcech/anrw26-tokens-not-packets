#!/usr/bin/env python3

import argparse
import re
import os
import multiprocessing

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import qlog_parser
import utils

def parse_qlog(args):
    path, regex = args

    matches = regex.search(path)
    if matches is None:
        print(f"regex did not match path '{path}'")
        return None

    qlog = qlog_parser.parse_qlog(path)
    lens = qlog.dpkt_rcvd[["streams", "fins"]].dropna()
    lens = lens.explode(["streams", "fins"])
    finished = lens[lens.fins]
    finished = finished.drop_duplicates('streams', keep='last')
    finished = finished[finished.streams != 0]
    if len(finished) != 16:
        print(f"Unexpected number of streams in {path}: {len(finished)}")
        return
    ct = finished.index.total_seconds() * 1000

    df = pd.DataFrame(dict(ct=ct, stream=finished.streams.values))

    for k, v in matches.groupdict().items():
        value = v
        try:
            value = int(v)
        except:
            pass
        df[k] = value

    return df

def plot_total_time(df, group_keys):
    df = df.set_index(group_keys)

    desc = df.groupby(group_keys).ct.describe().to_string()
    print(desc)

    schedulers = df.index.get_level_values(0).unique()
    utils.set_plt_style(len(schedulers))

    fig, ax = plt.subplots(figsize=(1.8,1.3))
    ax.set_ylabel("CDF")
    ax.set_xlabel("Stream Completion Time [ms]")
    for scheduler in schedulers:
        data = df.loc[scheduler, :].ct.values
        scheduler_label = utils.scheduler_label(scheduler)
        utils.plot_cdf(ax, data, label=scheduler_label)
    ax.legend()

    return fig

def plot_individual_time(df):
    # print(df.groupby(["scheduler"]).ct.describe())

    print(df.groupby(["scheduler", "stream"]).ct.describe())

    # df.groupby(["scheduler", "stream"]).ct.quantile([0.5, 0.9, 0.99])
    print(df.groupby(["scheduler", "stream"]).ct.quantile(0.99))

    schedulers = df.index.get_level_values(0).unique()
    utils.set_plt_style(len(schedulers))

    fig, ax = plt.subplots()
    ax.set_ylabel("CDF")
    ax.set_xlabel("Stream Completion Time [ms]")
    for scheduler in schedulers:
        data = df.loc[scheduler, :].ct.values
        breakpoint()
        scheduler_label = utils.scheduler_label(scheduler)
        utils.plot_cdf(ax, data, label=scheduler_label)
    ax.legend()

    return fig

def main():
    parser = argparse.ArgumentParser(description="Parse the receiver qlog to infer the stream completion time")
    parser.add_argument("qlogs", nargs="+", help="The receiver qlog files")
    parser.add_argument("--regex", required=True, help="Metadata regex with named groups")
    parser.add_argument("--group", nargs="+", default=["scheduler", "rep"], help="Scheduler should be first, rep last")
    parser.add_argument("--hide-ylabel", action="store_true")
    parser.add_argument("-o")
    args = parser.parse_args()

    regex = re.compile(args.regex)

    map_args = [(qlog, regex) for qlog in args.qlogs]

    # Use kkkk
    multiprocessing.set_start_method("spawn")
    df = utils.parse(parse_qlog, map_args, parallel=True)
    if df is None:
        return

    # group_keys = list(regex.groupindex.keys()) + ["rep"]

    figs = [plot_total_time(df, args.group)]

    if args.hide_ylabel:
        for fig in figs:
            fig.get_axes()[0].set_ylabel("")
            
            # plot_individual_time(df)]

    if args.o:
        with PdfPages(args.o) as pdf:
            for fig in figs:
                pdf.savefig(fig, bbox_inches="tight", pad_inches=0)
        # with open(os.path.splitext(args.o)[0] + ".txt", "w") as f:
        #     f.write(desc)
        #     f.write("\n")
    else:
        plt.show()

if __name__ == "__main__":
    main()
