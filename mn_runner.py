#!/usr/bin/env python3

from mininet.link import TCLink
from mininet.util import pmonitor
from mininet.clean import Cleanup

import argparse
import time
import os
import shutil
import itertools
import json
import signal
import sys
import shlex

import mp_topo

def param_to_option(side, k, v):
    # these options are not meant for quicheperf
    if k in ["repetition", "bw", "rtt", "loss", "queue"]:
        return ""

    # Client-only options
    if k in ["duration", "sizes", "streams", "bitrate"] and side == "server":
        return ""

    if k == "scheduler":
        scheduler_type = None
        schedulers = []
        scheduler_args = v.split(",")
        for scheduler_arg in scheduler_args:
            try:
                index = scheduler_arg.find("-") # for example "fscheduler-minrtt"
                arg = scheduler_arg[:index]
                scheduler = scheduler_arg[index+1:] # skip "-"
            except Exception as e:
                print(f"Bad 'scheduler' value: {v}\n{e}")
                sys.exit(1)

            if scheduler_type is None:
                scheduler_type = arg
            elif scheduler_type != arg:
                print(f"Can't mix schedulers of different types")
                sys.exit(1)

            schedulers.append(scheduler)
                 
        assert scheduler_type is not None

        schedulers = ",".join(schedulers)
        return f"--{scheduler_type}={schedulers}"

    return f"--{k.replace('_', '-')}={v}"

# Turns params that are list/tuple into string values
# for example: bw = [10, 10] -> 10-10
def format_config(dir_fmt, params):
    params_str = dict()
    for k, v in params.items():
        if type(v) in [list, tuple]:
            params_str[k] = "-".join([str(e) for e in v])
        else:
            params_str[k] = v
    return dir_fmt.format(**params_str)

def run_config(user, results_dir, experiment_name, config, continue_on_error):
    Cleanup.cleanup()

    os.makedirs(results_dir, exist_ok=True)
    base_path = os.path.join(results_dir, experiment_name)
    try:
        os.makedirs(base_path, exist_ok=False)
    except FileExistsError:
        print(f"The experiment results directory '{base_path}' already exists")
        return True

    shutil.chown(base_path, user, user)

    # Write config to disk for later inspection
    with open(f"{base_path}/config.json", "w") as f:
        json.dump(config, f, indent=4, sort_keys=True)

    # Check which params have multiple values to construct the directory name
    varied_params = [k for k, v in config.items() if len(v) > 1 and k != "repetition"]
    dir_fmt = "_".join([ "{" + k + "}" for k in varied_params])
    if dir_fmt == "":
        dir_fmt = "test"
    print(f"Directory output structure: {base_path}/{dir_fmt}/{{repetions}}")

    test_configs = list(itertools.product(*config.values()))

    test_durations = []
    for i, test_config in enumerate(test_configs):
        if run_test_config(config, dir_fmt, base_path, user, test_durations, test_configs, i, test_config, continue_on_error):
            return True
    return False

def run_test_config(config, dir_fmt, base_path, user, test_durations, test_configs, i, test_config, continue_on_error):
    test_start_ts = time.time()

    params = dict([(k,v) for k,v in zip(config.keys(), test_config)])

    # Path to directory for results of this iteration
    test_name = format_config(dir_fmt, params)
    results_path_base = os.path.join(base_path, test_name)
    results_path = os.path.join(results_path_base, f"{params['repetition']:02d}")
    os.makedirs(results_path, exist_ok=False)
    shutil.chown(results_path_base, user, user)
    shutil.chown(results_path, user, user)

    # Print estimated time remaining
    etr = 0
    if test_durations:
        etr = sum(test_durations)/len(test_durations) * (len(test_configs) - i)
    etr_min, etr_sec = divmod(etr, 60)
    print(f"\n#### [{i+1}/{len(test_configs)}] ETR={int(etr_min):02d}:{int(etr_sec):02d} min, test {test_name} {params}")

    try:
        failed = run_test(results_path, user, params)
    finally:
        finalize_results(results_path, user, test_name)

    test_durations.append(time.time() - test_start_ts)
    print(f"Test took {test_durations[-1]:.2f} s")

    if failed and not continue_on_error:
        print(f"Stopping due to failed test")
        return True
    if failed and continue_on_error:
        print(f"Test failed, try again")

        # Move to failed and try iteration again
        failed_path = os.path.join(base_path, test_name, "failed")
        os.makedirs(failed_path, exist_ok=True)
        shutil.move(results_path, failed_path)
        
        run_test_config(config, dir_fmt, base_path, user, test_durations, test_configs, i, test_config, continue_on_error)
        
    

def run_test(results_path, user, params):
    # Write the test-specific config to the result directory
    with open(f"{results_path}/config.json", "w") as f:
        json.dump(params, f, indent=4, sort_keys=True)

    topo = mp_topo.NtoNTopo(bw=params["bw"], rtt=params["rtt"], loss=params["loss"], queue=params["queue"])
    net = mp_topo.Mininet(topo=topo, link=TCLink)
    topo.setup_routing(net)

    net.start()
    time.sleep(1)

    client = net.get('h1')
    server = net.get('h2')

    env = dict(RUST_LOG="debug", # meaningless; it uses --logfile for logging
               QLOGDIR=results_path,
               STDERRDIR=results_path)
    server_env, client_env = env.copy(), env.copy()
    # client_env["SSLKEYLOGFILE"] = os.path.join(results_path, "key_client.log")
    # server_env["SSLKEYLOGFILE"] = os.path.join(results_path, "key_server.log")
    server_quicheperf_args = [param_to_option("server", k, v) for k,v in params.items()]
    client_quicheperf_args = [param_to_option("client", k, v) for k,v in params.items()]
    # if quicheperf_reverse:
    #     client_quicheperf_args.append("--reverse")

    # iso_ts = datetime.datetime.now().isoformat(timespec="seconds")
    # qdisc_file = open(os.path.join(results_path, f"{iso_ts}-qdisc-s1.csv"), "w")
    # qdisc_p = subprocess.Popen(["./parse_qdisc.py", "s1", "-i", "1"],
    #                            stdout=qdisc_file,
    #                            stderr=subprocess.PIPE)

    # p_tcpdump = client.popen(["tcpdump", "-i", "any", "-s", "120",
    #                          "-w", os.path.join(results_path, "client.pcap"),
    #                          "-Z", user])
    p_tcpdump = None

    server_cmd = ["sudo", "-u", user, "-E", "-s", "./mp_server.sh", "--"] + server_quicheperf_args
    client_cmd = ["sudo", "-u", user, "-E", "-s", "./mp_client.sh", "--"] + client_quicheperf_args

    p_server = server.popen(server_cmd, env=server_env)
    time.sleep(1)
    p_client = client.popen(client_cmd, env=client_env)
    output_blacklist = [" TRACE ", " INFO ", "Blocking waiting for file lock"]
    for host, line in pmonitor(dict(server=p_server, client=p_client), timeoutms=1000):
        if host and sum([v in line for v in output_blacklist]) == 0:
            print(f"[{host}] {line}", end='')
        # if host == "server" and "connection collected" in line:
        #     break
        # if host == "client" and "| Avg |" in line:
        #     time.sleep(1)
        #     break
        if p_client.poll() is not None or p_server.poll() is not None:
            print(f"Processes stopped: client={p_client.returncode}, server={p_server.returncode}")
            break

    time.sleep(1)

    failed = p_client.poll() != 0 or p_server.poll() != None
    if failed:
        print(f"Test failed: client={p_client.returncode}, server={p_server.returncode}")
        print(f"Client: {shlex.join(client_cmd)}")
        print(f"Server: {shlex.join(server_cmd)}")

    def print_stderr(role, ps):
        if ps.stderr:
            os.set_blocking(ps.stderr.fileno(), False)
            stderr = ps.stderr.read(10000)
            # if stderr and len(stderr) > 0:
            #     print(f"[{role}] stderr:\n{stderr.decode('utf-8')}\n")
            if stderr and len(stderr) > 0:
                for line in stderr.decode('utf-8').splitlines():
                    print(f"[{role} stderr] {line}")

    if p_client.poll() != 0:
        print_stderr("client", p_client)
    if p_client.poll() != None:
        print_stderr("server", p_server)

    # qdisc_p.send_signal(signal.SIGINT)

    time.sleep(1)
    # print(f"#### Terminate: client_pid={p_client.pid} server_pid={p_server.pid}")
    # os.system("pkill --signal SIGINT quicheperf")
    # p_client.kill()
    p_client.send_signal(signal.SIGINT)
    p_server.send_signal(signal.SIGINT)
    if p_tcpdump:
        p_tcpdump.kill()
    time.sleep(1)
    p_server.send_signal(signal.SIGINT)
    print("Waiting for p_client")
    p_client.wait()
    print("Waiting for p_server")
    p_server.wait()
    if p_tcpdump:
        print("Waiting for p_tcpdump")
        p_tcpdump.wait()

    # qdisc_file.flush()
    # qdisc_file.close()

    time.sleep(1)
    net.stop()
    time.sleep(1)

    return failed

def finalize_results(results_path, user, test_name):
    shutil.chown(results_path, user, user)
    for filename in os.listdir(results_path):
        new_filename = f"{test_name}-{filename}"
        src = os.path.join(results_path, filename)
        dst = os.path.join(results_path, new_filename)
        shutil.move(src, dst)
        shutil.chown(dst, user, user)

EXPERIMENTS = dict(
    sct = dict(
        # --- Mininet Topology ---
        rtt = [[10, 25]],
        loss = [[0, 0]],
        bw = [[10, 10]],
        queue = [[1000, 1000]],

        # --- quiche settings ---
        # duration = [4],

        # "fscheduler-roundrobin"
        scheduler = ["fscheduler-ecf", "fscheduler-saecf", "fscheduler-minrtt"],
        streams = [16],
        sizes = [100000],
    ),

    ack = dict(
        # --- Mininet Topology ---
        rtt = [[25, 10]],
        loss = [[0, 0]],
        bw = [[10, 10]],
        queue = [[1000, 1000]],
        max_data = [32 * 2 * 1000 * 1000],
        max_stream_data = [2 * 1000 * 1000],

        # --- quiche settings ---
        # duration = [4],

        scheduler = ["fscheduler-minrtt", "fscheduler-minrtt,fscheduler-cffast", "fscheduler-minrtt,fscheduler-acksamepath"],
        streams = [16],
        sizes = [10 * 1000, 100 * 1000, 1000 * 1000],
    ),
)

def main():
    parser = argparse.ArgumentParser(description="Run series of tests in mininet")
    parser.add_argument("user", help="The regular system user, i.e., $USER")
    parser.add_argument("experiment", help="The experiment name", choices=EXPERIMENTS.keys())
    parser.add_argument("--reps", help="How often to repeat the experiment", type=int, default=30)
    parser.add_argument("--results", help="The top-level results directory", default="results")
    parser.add_argument("--continue-on-error", help="Continue on error", action="store_true", default=False)
    args = parser.parse_args()

    # TODO: check if max stream data / max data is a problem

    config = EXPERIMENTS[args.experiment]
    config["repetition"] = [args.reps]

    if run_config(args.user, args.results, args.experiment, config, args.continue_on_error):
        sys.exit(1)

if __name__ == '__main__':
    main()
