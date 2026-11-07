# -*- coding: utf-8 -*-
"""
OSKen / OpenFlow 1.3 — Layer 2 Learning Switch

Save as controller.py and run with:
    osken-manager controller.py

Test in Mininet (controller IP replace <CONTROLLER_IP> if remote):
    sudo mn --topo single,3 --controller=remote,ip=<CONTROLLER_IP>,port=6653 --switch ovsk,protocols=OpenFlow13
    mininet> pingall
"""

from os_ken.base.app_manager import OSKenApp
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet
from os_ken.lib.dpid import dpid_to_str


class L2LearningSwitch(OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(L2LearningSwitch, self).__init__(*args, **kwargs)
        # mac_to_port: { dpid : { mac : port_no } }
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features_handler(self, ev):
        """
        Install table-miss flow to send unknown packets to controller.
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # match anyone, send to controller (no buffer so controller receives packet data)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.logger.info("Handshake with switch %s", dpid_to_str(datapath.id))
        # priority 0 = table-miss
        self.add_flow(datapath, priority=0, match=match, actions=actions)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        PacketIn handler: learn src MAC, decide out_port, install flow if possible,
        and send PacketOut.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Ensure per-switch table exists
        self.mac_to_port.setdefault(dpid, {})

        # Parse packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return  # non-ethernet packet

        src = eth.src
        dst = eth.dst

        # Note: in_port is provided in msg.match for OF1.3
        in_port = None
        try:
            in_port = msg.match['in_port']
        except Exception:
            # Fallback if match does not contain in_port
            if hasattr(msg, 'in_port'):
                in_port = msg.in_port

        if in_port is None:
            self.logger.warning("No in_port found in PacketIn from dpid=%s", dpid_to_str(dpid))
            return

        # Learn the source MAC -> port mapping
        self.mac_to_port[dpid][src] = in_port
        self.logger.debug("Learned %s -> %s on %s", src, in_port, dpid_to_str(dpid))

        # Determine output port
        out_port = None
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            self.logger.debug("Destination %s known on %s -> port %s", dst, dpid_to_str(dpid), out_port)
        else:
            # Unknown destination -> flood
            out_port = ofproto.OFPP_FLOOD
            self.logger.debug("Destination %s unknown on %s -> flooding", dst, dpid_to_str(dpid))

        # Build actions
        actions = [parser.OFPActionOutput(out_port)]

        # If destination is known and not broadcast, install a flow to avoid future PacketIns
        if out_port != ofproto.OFPP_FLOOD and dst != "ff:ff:ff:ff:ff:ff":
            match = parser.OFPMatch(eth_dst=dst)
            # You may also match eth_src if you want bi-directional pinned flows
            # match = parser.OFPMatch(eth_dst=dst, eth_src=src)
            # Install flow with a reasonable idle timeout (seconds)
            self.add_flow(datapath, priority=1, match=match, actions=actions, buffer_id=msg.buffer_id)
            self.logger.info("Installed flow: %s -> %s on %s", dst, out_port, dpid_to_str(dpid))

        # Prepare PacketOut: include data only if buffer_id == NO_BUFFER
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)
        return

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=300, hard_timeout=0):
        """
        Helper to add a flow on a datapath.

        If buffer_id is provided (not OFP_NO_BUFFER) the switch will apply the
        flow to that buffered packet as well.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id is not None and buffer_id != ofproto.OFP_NO_BUFFER:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst,
                                    idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath,
                                    priority=priority, match=match,
                                    instructions=inst,
                                    idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout)
        datapath.send_msg(mod)
