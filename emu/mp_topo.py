#!/usr/bin/env python3

import time
import argparse

from mininet.cli import CLI
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink


class MPTopo(Topo):
    """
    Parent abstract class which enables the child topologies to make the
hosts mptcp ready.
    """
    HOST_IP = '10.0.{0}.{1}'
    HOST_MAC = '00:00:00:00:{0:02x}:{1:02x}'

    TUN_IP = '11.0.0.{0}'

    def _setup_routing_per_host(self, host):
        # Manually set the ip addresses of the interfaces
        host_id = int(host.name[1:])

        for i, intf_name in enumerate(host.intfNames()):
            ip = self.HOST_IP.format(i+1, host_id)
            gateway = self.HOST_IP.format(i+1, 0)
            mac = self.HOST_MAC.format(i+1, host_id)

            # set IP and MAC of host
            host.intf(intf_name).config(ip='{}/24'.format(ip), mac=mac)

            # Don't setup routing for MPQUIC
            # host.cmd('ip rule add from {} table {}'.format(ip, i+1))
            # host.cmd('ip route add {}/24 dev {} scope link table {}'.format(gateway, intf_name, i+1))
            # host.cmd('ip route add default via {} dev {} table {}'.format(gateway, intf_name, i+1))

        host.cmd(f"ip route add default dev {host.intfNames()[0]}")
        print(f"ip route add default dev {host.intfNames()[0]}")
        

    def _setup_tun(self, host):
        host_id = int(host.name[1:])
        tun_ip = self.TUN_IP.format(host_id)

        host.cmd("sudo ip tuntap add mode tun multi_queue name mp0")
        host.cmd(f"ip addr add {tun_ip}/24 dev mp0")
        host.cmd("ip link set dev mp0 up")

    def start_sshd(self, host):
        host.cmd("sudo /usr/sbin/sshd -D &")

    def setup_routing(self, net):
        for host in self.hosts():
            h = net.get(host)
            self._setup_routing_per_host(h)
            self._setup_tun(h)


class NtoNTopo(MPTopo):
    """
    H1 and H2 have two network interfaces.

      /--- s1 --- s2 ---\
    h1                  h2
      \\--- s3 --- s4 ---/
    """

    # def build(self, *args, **kwargs):
    def build(self, bw=[10, 10], rtt=[50, 50], loss=[0, 0], queue=[1000, 1000]):
        # Add hosts and switches
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        self.addLink(h1, s1)
        self.addLink(h1, s3)

        linkopts = dict(use_tbf=False, use_htb=True)
        self.addLink(s1, s2, **linkopts, bw=bw[0], delay=f"{rtt[0]/2}ms", max_queue_size=queue[0], loss=loss[0])
        self.addLink(s3, s4, **linkopts, bw=bw[1], delay=f"{rtt[1]/2}ms", max_queue_size=queue[1], loss=loss[1])

        self.addLink(s2, h2)
        self.addLink(s4, h2)

class Nto1Topo(MPTopo):
    """
    H1 has two network interfaces connecting to the one interface of H2.

      /--- s1 ---\
    h1           s3 --- h2
      \\--- s2 ---/
    """

    # def build(self, *args, **kwargs):
    def build(self, bw=[10, 10], rtt=[50, 50], queue=[1000, 1000]):
        # Add hosts and switches
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        self.addLink(h1, s1)
        self.addLink(h1, s2)

        linkopts = dict(use_tbf=False, use_htb=True)
        self.addLink(s1, s3, **linkopts, bw=bw[0], delay=f"{rtt[0]/2}ms", max_queue_size=queue[0])
        self.addLink(s2, s3, **linkopts, bw=bw[1], delay=f"{rtt[1]/2}ms", max_queue_size=queue[1])

        self.addLink(s3, h2)

class ProxyTopo(MPTopo):
    """
    H1 has two network interfaces connecting to the one interface of H2.

      /--- s1 --\\        / --- h2
    h1           s3 --- s4
     \\--- s2 ---/       \\ --- h3
    """

    # def build(self, *args, **kwargs):
    def build(self, bw=[10, 10], rtt=[50, 50], queue=[1000, 1000]):
        # Add hosts and switches
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        self.addLink(h1, s1)
        self.addLink(h1, s2)

        linkopts = dict(use_tbf=False, use_htb=True)
        self.addLink(s1, s3, **linkopts, bw=bw[0], delay=f"{rtt[0]/2}ms", max_queue_size=queue[0])
        self.addLink(s2, s3, **linkopts, bw=bw[1], delay=f"{rtt[1]/2}ms", max_queue_size=queue[1])

        self.addLink(s3, s4)
        self.addLink(s4, h2)
        self.addLink(s4, h3)

class TestbedTopo(MPTopo):
    """
    H1 has two network interfaces connecting to the one interface of H2.

      /--- s1 --\\
    h1           s3 --- h2 --- s4 --- h3
     \\--- s2 ---/
    """

    def build(self, bw=[10, 10], rtt=[50, 50], queue=[1000, 1000]):
        # Add hosts and switches
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        self.addLink(h1, s1)
        self.addLink(h1, s2)

        linkopts = dict(use_tbf=False, use_htb=True)
        self.addLink(s1, s3, **linkopts, bw=bw[0], delay=f"{rtt[0]/2}ms", max_queue_size=queue[0])
        self.addLink(s2, s3, **linkopts, bw=bw[1], delay=f"{rtt[1]/2}ms", max_queue_size=queue[1])

        self.addLink(s3, h2)

        self.addLink(h2, s4)
        self.addLink(s4, h3)

available_topos = dict(nton=NtoNTopo, nto1=Nto1Topo, proxy=ProxyTopo, testbed=TestbedTopo)

def check_arg(arr):
    if type(arr) != list:
        raise Exception("expected list")
    if len(arr) == 1:
        return [arr[0], arr[0]]
    elif len(arr) == 2:
        return arr
    else:
        raise Exception(f"invalid number of options: {arr}")

def main():
    parser = argparse.ArgumentParser(description="Setup multipath mininet topology")
    # parser.add_argument("--config',  help='The config file', default='config.toml")
    parser.add_argument("--bw", help="Limit the bandwidth on the paths", type=int,
                        default=[10], nargs="*")
    parser.add_argument("--rtt", help="rtt on the paths in ms", type=int,
                        default=[50], nargs="*")
    parser.add_argument("--queue", help="queue size on the paths in number of packets", type=int,
                        default=[1000], nargs="*")
    parser.add_argument("--topo", help="Select the topology",
                        choices=available_topos.keys(),
                        default=list(available_topos.keys())[0])
    args = parser.parse_args()

    args.bw = check_arg(args.bw)
    args.rtt = check_arg(args.rtt)
    args.queue = check_arg(args.queue)

    # Start Mininet
    topo = available_topos[args.topo](bw=args.bw, rtt=args.rtt, queue=args.queue)
    net = Mininet(topo=topo, link=TCLink)

    # make sure every host has two IPs assigned
    topo.setup_routing(net)

    net.start()
    time.sleep(1)

    # # Test throughput for different configurations
    # for cc in ['lia', 'olia', 'balia', 'wvegas']:
    #     print('\n#### Testing bandwidth for {} (restriction on first leg: {})####'.format(cc, bw_on_first_leg))

    #     # set congestion control algoritm
    #     os.system('sysctl -w net.ipv4.tcp_congestion_control={}'.format(cc))

    #     # test bandwidth between the two hosts
    #     src = net.get('h1')
    #     dst = net.get('h2')
    #     serverbw, _clientbw = net.iperf([src, dst], seconds=10)
    #     # print('BW on Server: {}'.format(serverbw))

    # Open a CLI on each host
    # ps = [net.get(host).popen("alacritty") for host in ["h2", "h1"]]
    ps = [net.get(host).popen("alacritty") for host in topo.hosts()]

    topo.start_sshd(net.get("h2"))

    CLI(net)

    for p in ps:
        p.terminate()

    net.stop()


if __name__ == '__main__':
    main()
