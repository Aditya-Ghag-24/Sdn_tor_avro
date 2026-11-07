import os
import sys
import time
import json
import logging
import random
import networkx as nx
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, arp, ipv4, tcp
from os_ken.lib import hub

# Import AVRO logic
sys.path.append(os.getcwd())
from avro_logic import AVRO_SDN_Optimizer

class SuperAvroController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SuperAvroController, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.host_macs = {}
        self.path_cache = {} # FIX: Cache paths to stabilize handshakes
        self.gateway_mac = '00:00:00:00:00:fe'
        
        # PRE-LEARNED IDENTITIES (The "Chutney" Identity fix)
        # We map the Tor IPs to their expected container MACs to skip ARP delays
        self.host_macs['172.18.0.10'] = '02:42:ac:12:00:0a'
        self.host_macs['172.18.0.4'] = '02:42:ac:12:00:04'
        self.host_macs['172.18.0.5'] = '02:42:ac:12:00:05'
        self.host_macs['172.18.0.6'] = '02:42:ac:12:00:06' # Added tor_relay2

        
        # Initialize Topology Graph for AVRO
        self.graph = nx.Graph()
        for leaf in [4, 5, 6, 7]:
            for spine in [1, 2, 3]:
                self.graph.add_edge(leaf, spine, weight=random.uniform(1, 10))
        
        self.optimizer = AVRO_SDN_Optimizer(graph=self.graph)
        
        self.ip_to_switch = {}
        for i in range(1, 255):
            self.ip_to_switch[f'10.0.0.{i}'] = 4
            self.ip_to_switch[f'10.0.1.{i}'] = 5
            self.ip_to_switch[f'10.0.2.{i}'] = 6
            self.ip_to_switch[f'10.0.3.{i}'] = 7
            self.ip_to_switch[f'172.18.0.{i}'] = 6
        
        self.ip_to_switch['172.18.0.10'] = 5
        self.ip_to_switch['172.18.0.4'] = 6
        self.ip_to_switch['172.18.0.6'] = 6 # Added tor_relay2
        self.ip_to_switch['172.18.0.5'] = 7

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(datapath.ofproto.OFPP_CONTROLLER, datapath.ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst, idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth or eth.ethertype == 0x88cc: return

        # 1. ARP Handling (Passthrough Mode)
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.host_macs[arp_pkt.src_ip] = eth.src
            if arp_pkt.dst_ip.endswith('.254'):
                self.reply_arp(datapath, eth.src, arp_pkt.src_ip, arp_pkt.dst_ip, in_port)
                return
            
            dst_dpid = self.ip_to_switch.get(arp_pkt.dst_ip)
            if dst_dpid:
                target_dp = self.datapaths.get(dst_dpid)
                if target_dp:
                    # DYNAMIC PORT FIX: Use get_host_port instead of hardcoded 9
                    out_port = self.get_host_port(arp_pkt.dst_ip)
                    self.packet_out(target_dp, out_port, msg.data, target_dp.ofproto.OFPP_CONTROLLER)
                return
            return

        # 2. IPv4 Routing (AVRO Optimized)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            src_ip, dst_ip = ip_pkt.src, ip_pkt.dst
            dst_dpid = self.ip_to_switch.get(dst_ip)
            if not dst_dpid: return

            target_mac = self.host_macs.get(dst_ip)
            if not target_mac: return # Wait for ARP

            # STICKY AVRO PATH SELECTION: Use the Genetic Algorithm for ALL nodes,
            # but keep the path stable for 60s to ensure handshakes finish.
            cache_key = (src_ip, dst_ip)
            now = time.time()
            
            if cache_key in self.path_cache:
                path, timestamp = self.path_cache[cache_key]
                if now - timestamp > 60: # Path expires after 60s
                    path = self.optimizer.get_optimal_path(self.graph, datapath.id, dst_dpid)
                    self.path_cache[cache_key] = (path, now)
                    print(f"--- AVRO (Refresh): Routing {src_ip} -> {dst_ip} via {path} ---")
                else:
                    # Keep the sticky path
                    pass 
            else:
                # New connection: Calculate optimal path using AVRO
                path = self.optimizer.get_optimal_path(self.graph, datapath.id, dst_dpid)
                self.path_cache[cache_key] = (path, now)
                print(f"--- AVRO (New): Routing {src_ip} -> {dst_ip} via {path} ---")
            self.install_full_path(src_ip, dst_ip, target_mac, path)
            
            out_port = self.get_port(datapath.id, path[1]) if len(path) > 1 else self.get_host_port(dst_ip)
            self.packet_out(datapath, out_port, msg.data, in_port)

    def install_full_path(self, src_ip, dst_ip, dst_mac, path):
        for i in range(len(path)):
            dp = self.datapaths.get(path[i])
            if not dp: continue
            in_p = self.get_host_port(src_ip) if i == 0 else self.get_port(path[i], path[i-1])
            out_p = self.get_host_port(dst_ip) if i == len(path)-1 else self.get_port(path[i], path[i+1])
            actions = [dp.ofproto_parser.OFPActionOutput(out_p)]
            match = dp.ofproto_parser.OFPMatch(eth_type=0x0800, ipv4_src=src_ip, ipv4_dst=dst_ip, in_port=in_p)
            self.add_flow(dp, 10, match, actions, idle_timeout=60)

    def reply_arp(self, datapath, target_mac, target_ip, gateway_ip, port):
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(dst=target_mac, src=self.gateway_mac, ethertype=0x0806))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=self.gateway_mac, src_ip=gateway_ip, dst_mac=target_mac, dst_ip=target_ip))
        pkt.serialize()
        self.packet_out(datapath, port, pkt.data, datapath.ofproto.OFPP_CONTROLLER)

    def packet_out(self, datapath, port, data, in_port):
        actions = [datapath.ofproto_parser.OFPActionOutput(port)]
        out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER, in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def get_host_port(self, ip):
        if ip == '172.18.0.6': return 10 # tor_relay2
        if ip.startswith('172.18.0.'): return 9
        if ip.startswith('10.0.0.'): return int(ip.split('.')[3]) + 3
        last_octet = int(ip.split('.')[3])
        return 9 if last_octet == 100 else (last_octet if 1 <= last_octet <= 5 else None)

    def get_port(self, src, dst):
        port_map = {
            (1, 4): 1, (1, 5): 2, (1, 6): 3, (1, 7): 4,
            (2, 4): 1, (2, 5): 2, (2, 6): 3, (2, 7): 4,
            (3, 4): 1, (3, 5): 2, (3, 6): 3, (3, 7): 4,
            (4, 1): 1, (4, 2): 2, (4, 3): 3,
            (5, 1): 1, (5, 2): 2, (5, 3): 3,
            (6, 1): 1, (6, 2): 2, (6, 3): 3,
            (7, 1): 1, (7, 2): 2, (7, 3): 3
        }
        return port_map.get((src, dst))
