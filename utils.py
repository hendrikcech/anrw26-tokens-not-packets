#!/usr/bin/env python3

import multiprocessing
import random
from tqdm.auto import tqdm
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from cycler import cycler
try:
    from scipy.stats import bootstrap
except:
    pass

def parse(parse_fn, map_args, parallel=True, concat=True, cores=multiprocessing.cpu_count(), sample=None):
    map_args = random.sample(map_args, sample) if sample is not None else map_args
    if len(map_args) == 0:
        return None
    if parallel:
        threads = min(cores, len(map_args))
        with multiprocessing.Pool(threads) as pool:
            dfs = list(tqdm(pool.imap_unordered(parse_fn, map_args), total=len(map_args), desc="parsing"))
    else:
        dfs = list(tqdm(map(parse_fn, map_args), total=len(map_args)))
    if len(dfs) == 0:
        return None
    if concat:
        dfs_not_none = [df for df in dfs if df is not None]
        if len(dfs_not_none) == 0:
            print(f"All {len(dfs)} are None")
            return None
        return pd.concat(dfs_not_none)
    else:
        return [df for df in dfs if df is not None]

def plot_cdf(ax, data, ci=True, **kwargs):
    """
    Plots an emperical CDF in an (accurate) step-wise style (not smoothed).
    With ci=True (default), a 95% confidence interval is plotted which is
    estimated by bootstrapping.
    """
    x_grid = np.sort(data)
    n = len(data)
    y = np.arange(1, n + 1) / n
    
    if ci:
        # This function takes a resampled array and calculates the CDF 
        # at our fixed 'x_grid' points.
        def ecdf_statistic(resampled_data):
            # Sort the resampled batch
            sorted_sample = np.sort(resampled_data)

            # 'searchsorted' tells us how many items in the sample are <= x_grid
            # This effectively gives us the Cumulative Probability for the grid
            return np.searchsorted(sorted_sample, x_grid, side='right') / len(resampled_data)

        res = bootstrap((data,), 
                        ecdf_statistic, 
                        n_resamples=1000, 
                        confidence_level=0.95,
                        method="percentile", # BCa often fails
                        vectorized=False)

        ci_low = res.confidence_interval.low
        ci_high = res.confidence_interval.high

        ax.fill_between(x_grid, ci_low, ci_high, 
                        step="post", color=kwargs.get("color"), alpha=0.2)


    return ax.step(x_grid, y, where="post", **kwargs)[0]

FULL_WIDTH = 7.03 # acm double column textwidth 506.295pt = 7.03 inch;
COLUMN_WIDTH = 3.34 # single col 241.14749pt = 3.34 inch

def set_plt_style(n=6):
    pd.set_option("display.max_rows", 610)

    if n <= 6:
        # plt.style.use("petroff6")
        plt.style.use({
            "axes.prop_cycle": cycler('color', ['#5790fc', '#f89c20', '#e42536', '#964a8b', '#9c9ca1', '#7a21dd']),
            "patch.facecolor": "5790fc",
        })
    elif n <= 8:
        # plt.style.use("petroff8")
        plt.style.use({
            "axes.prop_cycle": cycler('color', ['#1845fb', '#ff5e02', '#c91f16', '#c849a9', '#adad7d', '#86c8dd', '#578dff', '#656364']),
            "patch.facecolor": "1845fb",
        })
    elif n <= 10:
        plt.style.use("petroff10")
    else:
        plt.style.use("petroff10")
        print(f"petroff10 colormap does not support enough colors!")

    params = {
        "axes.grid": True,
        "grid.alpha":     0.5, # 1.0
        "figure.figsize": (COLUMN_WIDTH, 1.5),  # (6.4, 4.8)
        # "font.family": "Linux Libertine O",
        "font.family": "Linux Biolinum O",
        "font.size": 8,
        "axes.titlepad": 4.0,      # 6.0 pad between axes and title in points
        "axes.labelpad": 2.0,      # 4.0 space between label and axis

        "legend.labelspacing": 0.25, # 0.5  # the vertical space between the legend entries
        "legend.handlelength":  1.25,  # 2.0, the length of the legend lines
        "legend.handletextpad": 0.4,  # 0.8, the space between the legend line and legend text
        ## Dimensions as fraction of font size:
        #legend.borderpad:     0.4  # border whitespace
        #legend.labelspacing:  0.5  # the vertical space between the legend entries
        #legend.handlelength:  2.0  # the length of the legend lines
        #legend.handleheight:  0.7  # the height of the legend handle
        #legend.handletextpad: 0.8  # the space between the legend line and legend text
        #legend.borderaxespad: 0.5  # the border between the axes and legend edge
        "legend.columnspacing": 1.0,  # 2.0  # column separation

        "savefig.bbox": "tight",
        "figure.constrained_layout.use": True,

        "figure.dpi": 300,
    }
    plt.style.use(params)

def scheduler_label(args, only_schedlet=True):
    """
    arg like
    - "fscheduler-minrtt"
    - "fscheduler-priostream-2"
    - "fscheduler-minrtt,fscheduler-priostream-2"
    """
    parts = args.split(",")
    if only_schedlet:
        labels = [single_scheduler_label(parts[-1])]
    else:
        labels = [single_scheduler_label(arg) for i, arg in enumerate(parts)]
    return " ".join(labels)
        

def single_scheduler_label(scheduler):
    try:
        index = scheduler.find("-")
    except:
        return scheduler

    scheduler = scheduler[index+1:] # skip "-"
    if scheduler.lower() == "minrtt":
        return "MinRTT"
    if scheduler.lower() == "roundrobin":
        return "RR"
    if scheduler.lower().startswith("reinjectstream"):
        sid = scheduler.split("-")[1]
        return f"ReinjectStream-{sid}"
    if scheduler.lower().startswith("redundantstream"):
        sid = scheduler.split("-")[1]
        return f"RedundantStream-{sid}"
    if scheduler.lower() == "acksamepath":
        return "Same Path"
    if scheduler.lower() == "cffast":
        return "Fast Path"
    if scheduler.lower() == "saecf":
        return "SA-ECF"
    return scheduler.upper()
