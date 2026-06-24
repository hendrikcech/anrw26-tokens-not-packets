#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy",
#     "pandas",
#     "pysimdjson",
# ]
# ///

# import json
import simdjson as json
import pandas as pd
from types import SimpleNamespace
import zstandard
import sys
import os
import dataclasses
import multiprocessing
import time

def print_func_time(func):
    return func # disable decorator
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        end = time.time()
        print(f"ran {func.__name__} in {int((end - start) * 1000)} ms")
        return res
    if hasattr(func, "__name__"):
        wrapper.__name__ = func.__name__
    else:
        wrapper.__name__ = func.fget.__name__
    return wrapper

@print_func_time
def dcs_to_df(dcs, dc_class):
    try:
        data = [dataclasses.astuple(dc) for dc in dcs]
    except:
        breakpoint()
    cols = [v.name for v in dataclasses.fields(dc_class)]
    df = pd.DataFrame(data, columns=cols).set_index("ts")
    return df.set_index(pd.to_timedelta(df.index, unit="ms"))

@dataclasses.dataclass
class DataPacket:
    ts: float
    path_id: int
    pktnum: int
    streams: list[int] | None
    fins: list[bool] | None
    data_blocked_limit: int | None
    max_data: int | None
    stream_0_blocked_limit: int | None
    stream_0_max_data: int | None
    stream_0_offset: int | None
    stream_0_length: int | None
    dgram_lengths: list[int] | None

    def from_qlog(o):
        header = o["data"]["header"]
        return DataPacket(ts=o["time"],
                          path_id=o["path_id"] if "path_id" in o else 0,
                          pktnum=header["packet_number"],
                          stream_0_blocked_limit=None,
                          data_blocked_limit=None,
                          fins=None,
                          max_data=None,
                          streams=None,
                          stream_0_max_data=None,
                          stream_0_offset=None, stream_0_length=None,
                          dgram_lengths=None)

    def __setattr__(self, name, value):
        if name in self.__dict__ and self.__dict__[name] is not None:
            raise Exception(f"Field {name} was already set to {self.__dict__[name]}")
        self.__dict__[name] = value

@dataclasses.dataclass
class ACK:
    ts: float
    path_id: int
    pktnum: int
    ack_path_id: int | None
    acked_ranges: list[tuple[int,int]] | None

    def from_qlog(o):
        header = o["data"]["header"]
        return ACK(ts=o["time"], path_id=o["path_id"] if "path_id" in o else 0,
                          pktnum=header["packet_number"], ack_path_id=None, acked_ranges=None)

# class MoveEntity(Enum):
#     application = 1,
#     transport =
#     dropped = 3,

@dataclasses.dataclass
class DataMove:
    ts: float
    stream: int
    offset: int
    length: int
    fr: str
    to: str

    def from_qlog(o):
        d = o["data"]
        return DataMove(ts=o["time"], stream=d["stream_id"], offset=d["offset"], length=d["length"],
                        fr=d["from"], to=d["to"])

@dataclasses.dataclass
class RecoveryMetric:
    ts: float
    path_id: int
    min_rtt: float | None
    smoothed_rtt: float | None
    latest_rtt: float | None
    rtt_variance: float | None
    cwnd: int | None
    bif: int | None
    ssthresh: int | None
    pacing_rate: int | None
    ack_delay: int | None

    def from_qlog(o, prev=None):
        d = o["data"]
        def val(key, class_attr=None):
            if prev is None:
                return d[key] if key in d else None
            else:
                if class_attr is None:
                    class_attr=key
                return d[key] if key in d else prev.__getattribute__(class_attr)
        obj = RecoveryMetric(ts=o["time"],
                             path_id=o["path_id"] if "path_id" in o else 0,
                             min_rtt=val("min_rtt"),
                             smoothed_rtt=val("smoothed_rtt"),
                             latest_rtt=val("latest_rtt"),
                             rtt_variance=val("rtt_variance"),
                             cwnd=val("congestion_window", "cwnd"),
                             bif=val("bytes_in_flight", "bif"),
                             ssthresh=val("ssthresh"),
                             pacing_rate=val("pacing_rate"),
                             ack_delay=val("ack_delay"))
        return obj

@dataclasses.dataclass
class FlowControl:
    ts: float
    stream: int
    max_data: int | None
    window: int | None
    max_window: int | None
    consumed: int | None
    app_offset: int | None
    max_offset: int | None

    def from_qlog(o, prev=None):
        d = o["data"]
        return FlowControl(ts=o["time"],
                           stream=d["stream_id"] if "stream_id" in d else -1,
                           max_data=d["max_data"] if "max_data" in d else None,
                           window=d["window"] if "window" in d else None,
                           max_window=d["max_window"] if "max_window" in d else None,
                           consumed=d["consumed"] if "consumed" in d else None,
                           app_offset=d["app_offset"] if "app_offset" in d else None,
                           max_offset=d["max_offset"] if "max_offset" in d else None)

@dataclasses.dataclass
class PacketLoss:
    # {'time': 355.37833, 'name': 'recovery:packet_lost', 'data': {'header': {'packet_type': '1RTT', 'packet_number': 153}, 'trigger': 'time_threshold'}}
    ts: float
    path_id: int
    pktnum: int
    trigger: str

    def from_qlog(o):
        return PacketLoss(ts=o["time"],
                          path_id=o["path_id"] if "path_id" in o else 0,
                          pktnum=o["data"]["header"]["packet_number"],
                          trigger=o["data"]["trigger"])

@dataclasses.dataclass
class PathStatus:
    # {"time":32807.21,"path_id":0,"name":"transport:packet_sent","data":{"header":{"packet_type":"1RTT","packet_number":14181},"raw":{"length":1350,"payload_length":1311},"send_at_time":32807.21,"frames":[...,{"frame_type":"path_status","dcid_seq_num":0,"seq_num":16,"status":2},...]}}
    ts: float
    path_id: int | None
    status: int | None
    advertised: bool | None

    def from_qlog(o):
        d = o["data"]
        return PathStatus(ts=o["time"],
                          path_id=d["path_id"] if "path_id" in d else None,
                          status=d["status"] if "status" in d else None,
                          advertised=d["advertised"] if "advertised" in d else None)

def get_packet_type(o):
    try:
        return o["data"]["header"]["packet_type"] # cl-quiche / sqlog
    except:
        return o["data"]["packet_type"] # mvfst / qlog


def parse_qlog_events_into(reader, res, options):
    dpkt_rcvd = []
    dpkt_sent = []
    mpack_rcvd = []
    mpack_sent = []
    recovery = []
    flow_control = []
    data_move = []
    lost = []
    path_stati = []
    start_time = None
    transport_params = {}
    reference_time = None # Interpret each event's timestamp as an offset to this time

    for o in reader:
        if o["category"] == "other" and o["event"] == "other" and "description" in o["data"]:
            # parse quicperf: "description":"quicperf id=1f46827746b2cb6df90e6f0ec41350b874126796 start_time=2022-12-08T17:44:02.185064659+01:00 peer_addr=3.70.11.248:8000"
            for item in o["data"]["description"].split(" "):
                parts = item.split("=")
                if parts[0] == "start_time":
                    start_time = pd.to_datetime(parts[1], format="%Y-%m-%dT%H:%M:%S.%f%z")

        o["time"] = options.format_ts(o["time"])
        if options.from_sec is not None and o["time"] < options.from_sec:
            continue
        if options.until_sec is not None and o["time"] > options.until_sec:
            break

        # Store local transport parameters. What is happening with the peer's transport parameters?
        if o["category"] == "transport" and o["event"] == "parameters_set":
            transport_params[o["data"]["owner"]] = o["data"] # owner: local or remote

        if o["category"] == "recovery" and (o["event"] == "metrics_updated" or (o["event"] == "metric_update")):
            # cf-quiche: metrics_updated, mvfst: metric_update
            rcvry = RecoveryMetric.from_qlog(o)
            options.format_recovery_metric(rcvry)
            recovery.append(rcvry)

        if o["category"] == "recovery" and o["event"] == "packet_lost":
            lost.append(PacketLoss.from_qlog(o))
            continue

        if o["category"] == "recovery" and o["event"] in ["stream_flow_control_updated", "connection_flow_control_updated", "recv_buf_updated"]:
            flow_control.append(FlowControl.from_qlog(o))

        if o["category"] == "transport" and o["event"] == "data_moved":
            data_move.append(DataMove.from_qlog(o))
            continue

        if o["category"] == "transport" and o["event"] == "path_status_updated":
            path_stati.append(PathStatus.from_qlog(o))
            continue

        if "header" not in o["data"] or get_packet_type(o) != "1RTT":
            continue

        dpkt = DataPacket.from_qlog(o)

        for frame in o["data"]["frames"]:
            if frame["frame_type"] == "stream":
                if not dpkt.streams:
                    dpkt.streams = list()
                dpkt.streams.append(frame["stream_id"])
                if int(frame["stream_id"]) == options.main_stream_id:
                    try:
                        dpkt.stream_0_offset = frame["offset"]
                        dpkt.stream_0_length = frame["length"]
                    except:
                        print(f"Packet contained two stream 0 frames: {o}")
                # dirty: If the packet contains multiple streams, it can also contain multiple fin values
                if not dpkt.fins:
                    dpkt.fins = []
                dpkt.fins.append(frame["fin"] if "fin" in frame else False)

            elif frame["frame_type"] == "data_blocked":
                # cl-quiche / sqlog: "limit", mvfst / qlog: "data_limit"
                dpkt.data_blocked_limit = frame["limit"] if "limit" in frame else "data_limit"
            elif frame["frame_type"] == "stream_data_blocked" and int(frame["stream_id"]) == options.main_stream_id:
                dpkt.stream_0_blocked_limit = frame["limit"]

            elif frame["frame_type"] == "max_data":
                # cl-quiche / sqlog: "maximum", mvfst / qlog: "maximum_data"
                dpkt.max_data = frame["maximum"] if "maximum" in frame else frame["maximum_data"]
            elif frame["frame_type"] == "max_stream_data" and int(frame["stream_id"]) == options.main_stream_id:
                dpkt.stream_0_max_data = frame["maximum"]

            elif frame["frame_type"] == "ack_mp" or frame["frame_type"] == "ack":
                ack = ACK.from_qlog(o)
                if frame["frame_type"] == "ack_mp":
                    ack.ack_path_id = frame["space_identifier"]
                else:
                    ack.ack_path_id = 0
                ack.acked_ranges = frame["acked_ranges"]
                if o["category"] == "transport" and o["event"] == "packet_received":
                    mpack_rcvd.append(ack)
                elif o["category"] == "transport" and o["event"] == "packet_sent":
                    mpack_sent.append(ack)

            elif frame["frame_type"] == "datagram":
                if not dpkt.dgram_lengths:
                    dpkt.dgram_lengths = [frame["length"]]
                else:
                    dpkt.dgram_lengths.append(frame["length"])

        if o["category"] == "transport" and o["event"] == "packet_received":
            dpkt_rcvd.append(dpkt)
        elif o["category"] == "transport" and o["event"] == "packet_sent":
            dpkt_sent.append(dpkt)

    res["dpkt_rcvd"]=dcs_to_df(dpkt_rcvd, DataPacket)
    res["dpkt_sent"]=dcs_to_df(dpkt_sent, DataPacket)
    res["mpack_rcvd"]=dcs_to_df(mpack_rcvd, ACK)
    res["mpack_sent"]=dcs_to_df(mpack_sent, ACK)
    res["recovery"]=dcs_to_df(recovery, RecoveryMetric)
    res["flow_control"]=dcs_to_df(flow_control, FlowControl)
    res["lost"]=dcs_to_df(lost, PacketLoss)
    res["data_move"]=dcs_to_df(data_move, DataMove)
    res["path_status"]=dcs_to_df(path_stati, PathStatus)
    res["start_time"]=start_time
    res["transport_params"]=transport_params

def readlines_zst(path):
    with zstandard.open(path, encoding="utf-8") as zf:
        previous_line = ""
        while True:
            chunk = zf.read(16000)
            if not chunk:
                break
            chunk_str = chunk.decode("utf-8")
            lines = chunk_str.split("\n")
            for i, line in enumerate(lines[:-1]):
                if i == 0:
                    line = previous_line + line
                yield line
            previous_line = lines[-1]
        yield previous_line

def readlines_uncompressed(path):
    with open(path, "rb") as f:
        for line in f.readlines():
            yield line.decode("utf-8")

def sqlog_parser(reader):
    for line in reader:
        try:
            if line[0] == "\x1e":
                # cl-quiche preprends 0x1e ("^^" in less) to each line
                line = line[1:]
            o = json.loads(line)
        except Exception as e:
            print(f"SQLOG JSON error: {e} at {line}", file=sys.stderr)
            continue
        if type(o) is not dict:
            continue
        if "name" not in o:
            yield dict(time=0.0, category="other", event="other", path_id=0, data=o)
        else:
            category, event = o["name"].split(":")
            path_id = o["path_id"] if "path_id" in o else 0
            yield dict(time=o["time"], category=category, event=event, path_id=path_id, data=o["data"])

def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def qlog_parser(o):
    if len(o["traces"]) > 1:
        print("qlog contains more than 1 trace. Only parsing first trace.", file=sys.stderr)
    if len(o["traces"]) == 0:
        return
    t = o["traces"][0]
    for ev in t["events"]:
        yield dict(time=ev[0], category=ev[1], event=ev[2], path_id=0, data=ev[3])

class DefaultOptions:
    def __init__(self):
        self.main_stream_id = 0
        self.from_sec = None
        self.until_sec = None

    def format_ts(self, ts):
        return ts

    def format_recovery_metric(self, rcvry):
        pass

class MvfstOptions(DefaultOptions):
    def __init__(self):
        self.first_ts = None
        self.main_stream_id = 3

    def format_ts(self, ts):
        # mvfst uses timestamps of an arbitrary timescale that don't start at 0
        if self.first_ts is None:
            self.first_ts = int(ts)
        return (int(ts) - self.first_ts) / 1000

    def format_recovery_metric(self, rcvry):
        if rcvry.min_rtt:
            rcvry.min_rtt /= 1000
        if rcvry.smoothed_rtt:
            rcvry.smoothed_rtt /= 1000
        if rcvry.latest_rtt:
            rcvry.latest_rtt /= 1000
        if rcvry.rtt_variance:
            rcvry.rtt_variance /= 1000

@print_func_time
def parse_qlog_into(path, result, from_sec=None, until_sec=None):
    qlogfmt = None
    part0, ext0 = os.path.splitext(path)
    compressed = ext0.startswith(".zst")
    if compressed:
        _, ext1 = os.path.splitext(part0)
        qlogfmt = ext1.lower()
    else:
        qlogfmt = ext0.lower()

    file_reader = None
    match (qlogfmt, compressed):
        case (".qlog", False):
            file_reader = read_json(path)
        case (".qlog", True):
            raise Exception("not yet implemented")
        case (".sqlog", False):
            file_reader = readlines_uncompressed(path)
        case (".sqlog", True):
            file_reader = readlines_zst(path)
        case _:
             print(f"Can't parse {path}")
             return None

    parser = None
    if qlogfmt == ".qlog":
        parser = qlog_parser(file_reader)
    elif qlogfmt == ".sqlog":
        parser = sqlog_parser(file_reader)

    options = DefaultOptions()
    if qlogfmt == ".qlog" and file_reader["title"].startswith("mvfst"):
            options = MvfstOptions()
    options.from_sec = from_sec
    options.until_sec = until_sec

    print(f"Parsing {path} ...", file=sys.stderr)
    parse_qlog_events_into(parser, result, options=options)

def parse_qlog(path, **kwargs):
    '''Helper function around parse_qlog_into() to avoid unidomatic passing and
    converting of objects that is necessary to use multiprocessing'''
    result = {}
    parse_qlog_into(path, result, **kwargs)
    if len(result) == 0:
        return None
    return FormattedSimpleNamespace(**result)

def parse_qlogs(paths, **kwargs): # object
    if type(paths) != dict:
        raise Exception("paths is expected to be an object mapping name to path")
    manager = multiprocessing.Manager()
    result = {}
    ps = []
    for key, path in paths.items():
        result[key] = manager.dict()
        ps.append(multiprocessing.Process(target=parse_qlog_into, args=(path, result[key]),
                                          kwargs=kwargs))
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    for k in result.keys():
        result[k] = FormattedSimpleNamespace(**result[k])
    return result

def parse_queue(path, start_time=None):
    df = pd.read_csv(path, names=["datetime", "dropped", "queue_p", "queue_b"],
                     parse_dates=["datetime"])
    if start_time:
        df = df.set_index("datetime").tz_localize(start_time.tz).reset_index()
        df.set_index(df["datetime"] - start_time, inplace=True)
    else:
        df.set_index("datetime", inplace=True)
    return df

class FormattedSimpleNamespace(SimpleNamespace):
    """Adds newlines to the string representation to make pandas dataframes
    better readable.

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("--- {} ---\n{!r}".format(k, self.__dict__[k]) for k in keys)
        return "\n".join(items)
