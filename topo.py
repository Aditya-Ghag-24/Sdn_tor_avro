from containernet.net import Containernet
from containernet.node import Docker
from containernet.cli import CLI
from containernet.term import makeTerm
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.node import RemoteController
import os

def setup_network():
    net = Containernet(controller=RemoteController)
    info('*** Adding Remote Controller\n')
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    info('*** Building network\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
    s5 = net.addSwitch('s5')
    s6 = net.addSwitch('s6')
    s7 = net.addSwitch('s7')

    info('*** Adding Tor Nodes (Identity Wipe Mode)\n')
    tor_cli = net.addDocker('tor_cli', ip='10.0.0.16/8', 
                            dimage="antitree/private-tor:latest", 
                            network_mode='none',
                            volumes=["/home/vboxuser/tor_avro/configs/client:/etc/tor:rw"])
    
    tor_relay = net.addDocker('tor_relay', ip='10.0.0.17/8', 
                              dimage="antitree/private-tor:latest", 
                              network_mode='none',
                              volumes=["/home/vboxuser/tor_avro/configs/relay:/etc/tor:rw"])

    tor_relay2 = net.addDocker('tor_relay2', ip='10.0.0.19/8', 
                              dimage="antitree/private-tor:latest", 
                              network_mode='none',
                              volumes=["/home/vboxuser/tor_avro/configs/relay2:/etc/tor:rw"])
    
    tor_hsdir = net.addDocker('tor_hsdir', ip='10.0.0.18/8', 
                              dimage="antitree/private-tor:latest", 
                              network_mode='none',
                              volumes=["/home/vboxuser/tor_avro/configs/hsdir:/etc/tor:rw"])

    info('*** Creating links\n')
    for leaf in [s4, s5, s6, s7]:
        for spine in [s1, s2, s3]:
            net.addLink(leaf, spine, cls=TCLink, delay='10ms', bw=10)

    # Adding the 15 Z-group hosts with explicit 10.0.0.x IPs
    host_count = 1
    for prefix in ['za', 'zb', 'zc']:
        for i in range(1, 6):
            h_name = f'{prefix}_h{i}'
            ip_addr = f'10.0.0.{host_count}/8'
            net.addHost(h_name, ip=ip_addr)
            net.addLink(h_name, s4)
            host_count += 1

    net.addLink(tor_cli, s5, port2=9)
    net.addLink(tor_relay, s6, port2=9)
    net.addLink(tor_relay2, s6, port2=10) # Both relays on S6
    net.addLink(tor_hsdir, s7, port2=9)

    info('*** Starting Network\n')
    net.start()

    info('*** Performing Identity Wipe and Manual Configuration\n')
    tor_configs = [
        ('tor_cli', '172.18.0.10/16', '172.18.0.254'),
        ('tor_relay', '172.18.0.4/16', '172.18.0.254'),
        ('tor_relay2', '172.18.0.6/16', '172.18.0.254'),
        ('tor_hsdir', '172.18.0.5/16', '172.18.0.254')
    ]
    
    for name, ip, gw in tor_configs:
        info(f'  Wiping and configuring {name} on {name}-eth0...\n')
        node = net.get(name)
        intf = node.intfNames()[0]
        node.cmd(f'ip addr flush dev {intf}')
        node.cmd(f'ip addr add {ip} dev {intf}')
        node.cmd(f'ip link set {intf} up')
        node.cmd('ip link set lo up')
        node.cmd(f'ip route add default via {gw} dev {intf}')
        node.cmd('mkdir -p /var/lib/tor && chmod 700 /var/lib/tor && rm -rf /var/lib/tor/*')
        node.cmd('rm -f /etc/tor/lock /etc/tor/state /etc/tor/cached-*')
        node.cmd('tor -f /etc/tor/torrc > /etc/tor/tor.log 2>&1 &')

    info('\n--- Spine-Leaf Tor Network Ready ---\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    setup_network()
