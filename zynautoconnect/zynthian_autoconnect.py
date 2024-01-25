# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector
# 
# Autoconnect Jack clients
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
# ********************************************************************
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
# 
# ********************************************************************

import sys
import os
import jack
import copy
import logging
from time import sleep
from threading import Thread, Lock
from collections import OrderedDict

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config

# -------------------------------------------------------------------------------
# Configure logging
# -------------------------------------------------------------------------------

log_level = int(os.environ.get('ZYNTHIAN_LOG_LEVEL', logging.WARNING))

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

#if log_level==logging.DEBUG:
#	import inspect

# -------------------------------------------------------------------------------
# Define some Constants and Global Variables
# -------------------------------------------------------------------------------

jclient = None
thread = None
exit_flag = False

last_hw_str = None
max_num_devs = 16
devices_in = [None for i in range(max_num_devs)]
devices_in_name = [None for i in range(max_num_devs)]
devices_in_mode = [None for i in range(max_num_devs + 1)]
devices_out = [None for i in range(max_num_devs)]
devices_out_name = [None for i in range(max_num_devs)]

refresh_time = 0.1
mididev_refresh_time = 2
mididev_refresh_time_count = 0
mididev_changed = False

# ------------------------------------------------------------------------------


def get_port_alias_id(midi_port):
	try:
		alias_id = '_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id = midi_port.name

	if midi_port.is_input:
		postfix = "OUT"
	else:
		postfix = "IN"

	if alias_id.startswith("ttymidi:"):
		alias_id = f"DIN-5 MIDI-{postfix}"
	elif alias_id.startswith("a2j:"):
		alias_id = f"ALSA MIDI-{postfix}"
	elif alias_id == "f_midi":
		alias_id = f"USB MIDI-{postfix}"

	return alias_id


# Dirty hack for having MIDI working with PureData,  CSound, MOD-UI: #TODO => Improve it!!
def get_fixed_midi_port_name(port_name):
	if port_name == "pure_data":
		port_name = "Pure Data"

	elif port_name == "csound6":
		port_name = "Csound"

	elif port_name == "mod-monitor":
		port_name = "mod-host"

	return port_name


def get_all_connections_by_name(name):
	try:
		return jclient.get_all_connections(jclient.get_port_by_name(name))
	except:
		return []


# Connects the output port (port_from) to a list of input ports (ports_to), 
# disconnecting the output port from any other input port.
def connect_only(port_from, ports_to):
	# Get jack ports from strings if needed
	if isinstance(port_from, str):
		port_from = jclient.get_port_by_name(port_from)
	for i, pt in enumerate(ports_to):
		if isinstance(pt, str):
			ports_to[i] = jclient.get_port_by_name(pt)
	# Connect/disconnect
	for port_to in ports_to:
		already_connected = False
		for p in jclient.get_all_connections(port_from):
			if p == port_to:
				already_connected = True
			elif p not in ports_to:
				jclient.disconnect(port_from, p)
		if not already_connected:
			jclient.connect(port_from, port_to)


def replicate_connections_to(port1, port2):
	if isinstance(port1, str):
		port1 = jclient.get_port_by_name(port1)
	if isinstance(port2, str):
		port2 = jclient.get_port_by_name(port2)
	con1 = jclient.get_all_connections(port1)
	con2 = jclient.get_all_connections(port2)
	for p in con1:
		if p not in con2:
			jclient.connect(p, port2)
		else:
			con2.remove(p)
	for p in con2:
		jclient.disconnect(p, port2)


def get_midi_in_devid(idev):
	if 0 < idev <= len(devices_in):
		return devices_in[idev - 1]
	else:
		return None


def get_midi_out_devid(idev):
	if 0 < idev <= len(devices_out):
		return devices_out[idev - 1]
	else:
		return None


def get_midi_in_dev_mode(i):
	if 0 <= i < len(devices_in_mode):
		return devices_in_mode[i]
	else:
		return None


def update_midi_in_dev_mode(i):
	if 0 <= i < len(devices_in_mode):
		if lib_zyncore.zmip_get_flag_active_chan(i):
			devices_in_mode[i] = "ACTI"
		elif lib_zyncore.zmip_get_flag_omni_chan(i):
			devices_in_mode[i] = "OMNI"
		else:
			devices_in_mode[i] = "MULTI"


def update_midi_in_dev_mode_all():
	for i in range(len(devices_in_mode)):
		update_midi_in_dev_mode(i)


def set_mididev_changed(flag):
	global mididev_changed
	mididev_changed = flag


def get_mididev_changed():
	return mididev_changed

# ------------------------------------------------------------------------------


def midi_autoconnect(force=False):
	global mididev_refresh_time_count
	global last_hw_str

	# Get Mutex Lock
	acquire_lock()

	#logger.info("ZynAutoConnect: MIDI ...")

	# ------------------------------------
	# Get Input/Output MIDI Ports: 
	#  - outputs are inputs for jack
	#  - inputs are outputs for jack
	# ------------------------------------

	# Get Physical MIDI input ports ...
	hw_out = jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out) == 0:
		hw_out = []

	# Get Physical MIDI output ports ...
	hw_in = jclient.get_ports(is_input=True, is_physical=True, is_midi=True)
	if len(hw_in) == 0:
		hw_in = []

	# Add Aubio to MIDI input ports ...
	if zynthian_gui_config.midi_aubionotes_enabled:
		aubio_out = jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass

	#logger.debug("Input Device Ports: {}".format(hw_out))
	#logger.debug("Output Device Ports: {}".format(hw_in))

	# Calculate device list fingerprint (HW & virtual)
	hw_str = ""
	for hw in hw_out:
		hw_str += hw.name + "\n"
	for hw in hw_in:
		hw_str += hw.name + "\n"

	# Check for new devices (HW and virtual)...
	if hw_str != last_hw_str:
		last_hw_str = hw_str
		hw_str_changed = True
	else:
		hw_str_changed = False

	if not force and not hw_str_changed:
		mididev_refresh_time_count = 0
		#Release Mutex Lock
		release_lock()
		#logger.info("ZynAutoConnect: MIDI Shortened ...")
		return

	# Get Engines list from UI
	zyngine_list = zynthian_gui_config.zyngui.screens["engine"].zyngines

	# Get Engines MIDI input, output & feedback ports:
	engines_in = {}
	engines_out = []
	engines_fb = []
	for k, zyngine in zyngine_list.items():
		if not zyngine.jackname:
			continue

		if zyngine.type in ("MIDI Synth", "MIDI Tool", "Special"):
			port_name = get_fixed_midi_port_name(zyngine.jackname)
			#logger.debug("Zyngine Port Name: {}".format(port_name))

			ports = jclient.get_ports(port_name, is_input=True, is_midi=True, is_physical=False)
			try:
				#logger.debug("Engine {}:{} found".format(zyngine.jackname,ports[0].short_name))
				engines_in[zyngine.jackname] = ports[0]
			except:
				#logger.warning("Engine {} is not present".format(zyngine.jackname))
				pass

			ports = jclient.get_ports(port_name, is_output=True, is_midi=True, is_physical=False)
			try:
				#logger.debug("Engine {}:{} found".format(zyngine.jackname,ports[0].short_name))
				if zyngine.type == "MIDI Synth":
					engines_fb.append(ports[0])
				else:
					engines_out.append(ports[0])
			except:
				#logger.warning("Engine {} is not present".format(zyngine.jackname))
				pass

	#logger.debug("Synth Engine Input Ports: {}".format(engines_in))
	#logger.debug("Synth Engine Output Ports: {}".format(engines_out))
	#logger.debug("Synth Engine Feedback Ports: {}".format(engines_fb))

	# Get Zynthian Midi Router MIDI ports
	zmr_out = OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_output=True, is_midi=True):
		zmr_out[p.shortname] = p
	zmr_in = OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_input=True, is_midi=True):
		zmr_in[p.shortname] = p

	#logger.debug("ZynMidiRouter Input Ports: {}".format(zmr_out))
	#logger.debug("ZynMidiRouter Output Ports: {}".format(zmr_in))

	# ------------------------------------
	# Build routed-in (output) ports dict
	# ------------------------------------

	# Add engines_in
	routed_in = {}
	for pn, port in engines_in.items():
		routed_in[pn] = [port]

	# Add Zynmaster (CV/gate output)
	zmip = jclient.get_ports("ZynMaster:midi_in", is_input=True, is_physical=False, is_midi=True)
	try:
		routed_in["CV/Gate Out"] = [zmip[0]]
		port_alias_id = get_port_alias_id(zmip[0])
		enabled_hw_ports = {port_alias_id: zmip[0]}
	except:
		routed_in["CVGate-OUT"] = []
		enabled_hw_ports = {}

	# Add enabled Hardware ports 
	for hwp in hw_in:
		try:
			routed_in[hwp.name] = [hwp]
			port_alias_id = get_port_alias_id(hwp)
			if port_alias_id.replace(" ", "_") in zynthian_gui_config.enabled_midi_out_ports:
				enabled_hw_ports[port_alias_id] = hwp
		except:
			pass

	# Add enabled Network ports
	enabled_nw_ports = {}
	routed_in["NET-OUT"] = []
	for nwp in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge"):
		zmip = jclient.get_ports(nwp, is_input=True, is_physical=False, is_midi=True)
		try:
			port_alias_id = get_port_alias_id(zmip[0])
			if port_alias_id.replace(" ", "_") in zynthian_gui_config.enabled_midi_out_ports:
				routed_in["NET-OUT"].append(zmip[0])
				enabled_nw_ports[port_alias_id] = zmip[0]
		except:
			pass

	# ------------------------------------
	# Auto-Connect MIDI Ports
	# ------------------------------------

	# Connect MIDI Input Devices
	busy_idevs = []
	for hw in hw_out:
		devnum = None
		port_alias_id = get_port_alias_id(hw)
		if port_alias_id:
			#logger.debug("Connecting MIDI Input {}".format(hw))
			try:
				# If the device is marked as disabled, disconnect from all dev ports
				if port_alias_id in zynthian_gui_config.disabled_midi_in_ports:
					for i in range(16):
						jclient.disconnect(hw, zmr_in['dev{}_in'.format(i)])
				# else ...
				else:
					# if the device is already registered, takes the number
					try:
						devnum = devices_in.index(port_alias_id)
					# else registers it, taking the first free port
					except:
						for i in range(max_num_devs):
							if devices_in[i] is None:
								devnum = i
								devices_in[devnum] = port_alias_id
								devices_in_name[devnum] = hw.name
								update_midi_in_dev_mode(devnum)
								break
					if devnum is not None:
						busy_idevs.append(devnum)
						jclient.connect(hw, zmr_in['dev{}_in'.format(devnum)])
			except Exception as e:
				#logger.debug("Exception {}".format(e))
				pass
	# Delete disconnected input devices from list
	for i in range(max_num_devs):
		if i not in busy_idevs:
			devices_in[i] = None
			devices_in_name[i] = None
			devices_in_mode[i] = None

	# Connect MIDI Output Devices
	busy_idevs = []
	for hw in hw_in:
		devnum = None
		port_alias_id = get_port_alias_id(hw)
		if port_alias_id:
			#logger.debug("Connecting MIDI Output {}".format(hw))
			try:
				# if the device is already registered, takes the number
				try:
					devnum = devices_out.index(port_alias_id)
				# else registers it, taking the first free port
				except:
					for i in range(max_num_devs):
						if devices_out[i] is None:
							devnum = i
							devices_out[devnum] = port_alias_id
							devices_out_name[devnum] = hw.name
							break
				if devnum is not None:
					busy_idevs.append(devnum)
					jclient.connect(zmr_out['dev{}_out'.format(devnum)], hw)
			except Exception as e:
				#logger.debug("Exception {}".format(e))
				pass

	# Delete disconnected output devices from list
	for i in range(max_num_devs):
		if i not in busy_idevs:
			devices_out[i] = None
			devices_out_name[i] = None

	# Flag device list changes
	if hw_str_changed:
		set_mididev_changed(True)

	#logger.debug("Connecting RTP-MIDI & QMidiNet to ZynMidiRouter:net_in ...")

	# Connect RTP-MIDI output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_rtpmidi_enabled:
		try:
			jclient.connect("jackrtpmidid:rtpmidi_out", zmr_in['net_in'])
		except:
			pass

	# Connect QMidiNet output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_network_enabled:
		try:
			jclient.connect("QmidiNet:out_1", zmr_in['net_in'])
		except:
			pass

	# Connect TouchOSC output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_touchosc_enabled:
		try:
			jclient.connect("RtMidiOut Client:TouchOSC Bridge", zmr_in['net_in'])
		except:
			pass

	# Connect zynseq (stepseq) output to ZynMidiRouter:step_in
	try:
		jclient.connect("zynseq:output", zmr_in['step_in'])
	except:
		pass

	# Connect zynsmf output to ZynMidiRouter:seq_in
	try:
		jclient.connect("zynsmf:midi_out", zmr_in['seq_in'])
	except:
		pass

	#C onnect ZynMidiRouter:main_out to zynsmf input
	try:
		jclient.connect(zmr_out['main_out'], "zynsmf:midi_in")
	except:
		pass

	# Connect Engine's Controller-FeedBack to ZynMidiRouter:ctrl_in
	try:
		for efbp in engines_fb:
			jclient.connect(efbp, zmr_in['ctrl_in'])
	except:
		pass

	#logger.debug("Connecting ZynMidiRouter to engines ...")

	# Get zynthian layer manager object
	zynguilayer = zynthian_gui_config.zyngui.screens["layer"]

	# Get layer list
	layers_list = zynguilayer.layers

	# Connect MIDI chain elements
	for i, layer in enumerate(layers_list):
		if layer.get_midi_jackname() and layer.engine.type in ("MIDI Tool", "Special"):
			sport_name = get_fixed_midi_port_name(layer.get_midi_jackname())
			sports = jclient.get_ports(sport_name, is_output=True, is_midi=True, is_physical=False)
			if sports:
				#Connect to assigned ports and disconnect from the rest ...
				for mi, dports in routed_in.items():
					#logger.debug(" => Probing {} => {}".format(sport_name, mi))
					if mi in layer.get_midi_out():
						for dport in dports:
							#logger.debug(" => Connecting {} => {}".format(sport_name, mi))
							try:
								jclient.connect(sports[0], dport)
							except:
								pass
							try:
								jclient.disconnect(zmr_out['ch{}_out'.format(layer.midi_chan)], dport)
							except:
								pass
					else:
						for dport in dports:
							try:
								jclient.disconnect(sports[0], dport)
							except:
								pass


	# Connect ZynMidiRouter to MIDI-chain roots
	midichain_roots = zynguilayer.get_midichain_roots()

	# => Get Root-engines info
	root_engine_info = {}
	for mcrl in midichain_roots:
		for mcprl in zynguilayer.get_midichain_pars(mcrl):
			if mcprl.get_midi_jackname():
				jackname = mcprl.get_midi_jackname()
				if jackname in root_engine_info:
					root_engine_info[jackname]['chans'].append(mcprl.midi_chan)
				else:
					port_name = get_fixed_midi_port_name(jackname)
					ports = jclient.get_ports(port_name, is_input=True, is_midi=True, is_physical=False)
					if ports:
						root_engine_info[jackname] = {
							'port': ports[0],
							'chans': [mcprl.midi_chan]
						}

	for jn, info in root_engine_info.items():
		#logger.debug("MIDI ROOT ENGINE INFO: {} => {}".format(jn, info))
		if None in info['chans']:
			try:
				jclient.connect(zmr_out['main_out'], info['port'])
			except:
				pass
		else:
			for ch in range(16):
				try:
					if ch in info['chans']:
						jclient.connect(zmr_out['ch{}_out'.format(ch)], info['port'])
					else:
						jclient.disconnect(zmr_out['ch{}_out'.format(ch)], info['port'])
				except:
					pass

	# Set MIDI THRU
	lib_zyncore.set_midi_thru(zynthian_gui_config.midi_filter_output)

	# Connect MIDI-THRU output to enabled Hardware Output Ports
	for paid, hwport in enabled_hw_ports.items():
		try:
			jclient.connect(zmr_out['midi_out'], hwport)
		except:
			pass

	# Connect MIDI NET output to enabled Hardware Output Ports
	for paid, nwport in enabled_nw_ports.items():
		# Connect ZynMidiRouter:net_out to ...
		try:
			jclient.connect(zmr_out['net_out'], nwport)
		except:
			pass

	#C onnect ZynMidiRouter:step_out to ZynthStep input
	try:
		jclient.connect(zmr_out['step_out'], "zynseq:input")
	except:
		pass

	# Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for hw in hw_in:
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.enabled_midi_fb_ports:
				jclient.connect(zmr_out['ctrl_out'], hw)
			else:
				jclient.disconnect(zmr_out['ctrl_out'], hw)
		except:
			pass

	# Disconnect hardware inputs from mod-ui
	for sport in hw_out:
		try:
			jclient.disconnect(sport, 'mod-host:midi_in')
		except:
			pass

	mididev_refresh_time_count = 0
	# Release Mutex Lock
	release_lock()


def audio_autoconnect(force=False):
	if not force:
		#logger.debug("ZynAutoConnect: Audio Escaped ...")
		return

	# Get Mutex Lock
	#logger.info("Acquiring lock ...")
	acquire_lock()
	#logger.info("Lock acquired!!")

	# Get zynthian layer manager object
	zynguilayer = zynthian_gui_config.zyngui.screens["layer"]

	# Get Audio Input Ports (ports receiving audio => inputs => you write on it!!)
	input_ports = get_audio_input_ports(True)

	# Get System Playback Ports
	system_playback_ports = jclient.get_ports("system:playback", is_input=True, is_audio=True, is_physical=True)

	# Get Zynmixer Playback Ports
	zynmixer_playback_ports = jclient.get_ports("zynmixer", is_input=True, is_audio=True, is_physical=False)
	
	# Get Zynmixer Playback Ports
	playback_ports = zynmixer_playback_ports + system_playback_ports

	# Disconnect mod-ui from System Output
	mon_out = jclient.get_ports("mod-monitor", is_output=True, is_audio=True)
	try:
		jclient.disconnect(mon_out[0], 'system:playback_1')
		jclient.disconnect(mon_out[1], 'system:playback_2')
	except:
		pass

	# Get layers list from UI
	layers_list = zynguilayer.layers

	# Connect Engines to assigned outputs
	for layer_index, layer in enumerate(layers_list):
		if not layer.get_audio_jackname() or layer.engine.type == "MIDI Tool":
			continue

		layer_aout_ports = get_layer_audio_out_ports(layer)
		layer_playback_ports = [jn for jn in layer_aout_ports if jn.startswith("zynmixer") or jn.startswith("system:playback")]
		nlpb = len(layer_playback_ports)

		ports = jclient.get_ports(layer.get_audio_jackname(), is_output=True, is_audio=True, is_physical=False)
		if len(ports) > 0:
			#logger.debug("Connecting Layer {} ...".format(layer.get_jackname()))
			np = len(ports)
			#logger.debug("Num of {} Audio Ports: {}".format(layer.get_jackname(), np))

			# Connect layer to routed playback ports and disconnect from the rest ...
			if len(playback_ports) > 0:
				npb = min(nlpb, len(ports))
				for j, pbp in enumerate(playback_ports):
					if pbp.name in layer_playback_ports:
						for k, lop in enumerate(ports):
							if k % npb == j % npb:
								#logger.debug("Connecting {} to {} ...".format(lop.name, pbp.name))
								try:
									jclient.connect(lop, pbp)
								except:
									pass
							else:
								#logger.debug("Disconnecting {} from {} ...".format(lop.name, pbp.name))
								try:
									jclient.disconnect(lop, pbp)
								except:
									pass
					else:
						for lop in ports:
							#logger.debug("Disconnecting {} from {} ...".format(lop.name, pbp.name))
							try:
								jclient.disconnect(lop, pbp)
							except:
								pass

			# Connect to routed layer input ports and disconnect from the rest ...
			for ao in input_ports:
				nip = len(input_ports[ao])
				jrange = list(range(max(np, nip)))
				if ao in layer_aout_ports:
					#logger.debug("Connecting to {} : {}".format(ao,jrange))
					for j in jrange:
						try:
							psrc = ports[j % np]
							pdest = input_ports[ao][j % nip]
							#logger.debug("   ... {} => {}".format(psrc.name, pdest.name))
							jclient.connect(psrc, pdest)
						except:
							pass
				else:
					#logger.debug("Disconnecting from {} : {}".format(ao,jrange))
					for j in jrange:
						try:
							psrc = ports[j % np]
							pdest = input_ports[ao][j % nip]
							#logger.debug("   ... {} => {}".format(psrc.name, pdest.name))
							jclient.disconnect(psrc, pdest)
						except:
							pass

		# Connect MIDI to audio-FXs, if a MIDI input port exist (i.e. x42 AutoTune, MDA Vocoder)
		if layer.engine.type == "Audio Effect":
			midi_ports = jclient.get_ports(layer.get_midi_jackname(), is_input=True, is_midi=True, is_physical=False)
			if len(midi_ports) > 0:
				try:
					jclient.connect("ZynMidiRouter:ch{}_out".format(layer.midi_chan), midi_ports[0])
				except:
					pass

	# Connect metronome to aux
	try:
		jclient.connect("zynseq:metronome", "zynmixer:input_17a")
		jclient.connect("zynseq:metronome", "zynmixer:input_17b")
	except:
		pass

	# Connect mixer to the System Output
	try:
		jclient.connect("zynmixer:output_a", system_playback_ports[0])
		jclient.connect("zynmixer:output_b", system_playback_ports[1])
	except:
		pass

	# Replicate System Output connections to Headphones
	hp_ports = jclient.get_ports("Headphones:playback", is_input=True, is_audio=True)
	if len(hp_ports) >= 2:
		replicate_connections_to(system_playback_ports[0], hp_ports[0])
		replicate_connections_to(system_playback_ports[1], hp_ports[1])

	# Get System Capture ports => jack output ports!!
	capture_ports = get_audio_capture_ports()
	capture_ports += jclient.get_ports('zynmixer:send')
	capture_to_mixer = []
	root_layers = zynguilayer.get_fxchain_roots()
	# Connect audio inputs (capture or mixer send)
	for rl in root_layers:
		if rl.engine.nickname != "AI":
			continue

		rlp = get_layer_audio_out_ports(rl)
		rlp_ports = []
		for l in rlp:
			rlp_ports += jclient.get_ports(l, is_input=True, is_audio=True, is_physical=False)
		if len(rlp_ports) > 0:
			rl_in = rl.get_audio_in()
			nsc = min(len(rl_in), len(rlp_ports))

			# Connect System Capture to Root Layer ports
			for j, cp in enumerate(capture_ports):
				scp = cp.name
				if scp in rl_in:
					for k, rlp_inp in enumerate(rlp_ports):
						if rlp_inp.name.startswith("zynmixer:return") and scp.startswith("zynmixer:send"):
							continue  # Don't connect send to return - mixer does optimized normalisation when return disconnected
						if k % nsc == j % nsc:
							#logger.debug("Connecting {} to {} ...".format(scp.name, layer.get_audio_jackname()))
							try:
								jclient.connect(scp, rlp_inp)
							except:
								pass
						else:
							try:
								jclient.disconnect(scp, rlp_inp)
							except:
								pass
						# Limit to 2 input ports
						#if k>=1:
						#	break
				else:
					for rlp_inp in rlp_ports:
						try:
							jclient.disconnect(scp, rlp_inp)
						except:
							pass
		if "mixer" in rl.get_audio_out():
			capture_to_mixer.append(rl.midi_chan)

	# Clear unused direct connection from audio inputs to mixer
	for midi_chan in range(16):
		if midi_chan not in capture_to_mixer:
			for ip in capture_ports:
				try:
					jclient.disconnect(ip, "zynmixer:input_{:02d}a".format(midi_chan + 1))
				except:
					pass
				try:
					jclient.disconnect(ip, "zynmixer:input_{:02d}b".format(midi_chan + 1))
				except:
					pass

	if zynthian_gui_config.midi_aubionotes_enabled:
		# Get Aubio Input ports...
		aubio_in = jclient.get_ports("aubio", is_input=True, is_audio=True)
		if len(aubio_in) > 0:
			nip = len(aubio_in)
			# Connect System Capture to Aubio ports
			j = 0
			for scp in capture_ports:
				try:
					jclient.connect(scp, aubio_in[j % nip])
				except:
					pass
				j += 1

	# Release Mutex Lock
	release_lock()


# Connect mixer to the ffmpeg recorder
def audio_connect_ffmpeg(timeout=2.0):
	t = 0
	while t < timeout:
		try:
			jclient.connect("zynmixer:output_a", "ffmpeg:input_1")
			jclient.connect("zynmixer:output_b", "ffmpeg:input_2")
			return
		except:
			sleep(0.1)
			t += 0.1


def audio_connect_aux(source_name):
	ports = jclient.get_ports(source_name, is_output=True, is_audio=True)
	if ports:
		try:
			if len(ports) > 1:
				jclient.connect(ports[0], "zynmixer:input_17a")
				jclient.connect(ports[1], "zynmixer:input_17b")
			else:
				jclient.connect(ports[0], "zynmixer:input_17a")
				jclient.connect(ports[0], "zynmixer:input_17b")
		except Exception as e:
			logging.error("Can't connect {} to audio aux ports".format(source_name), e)


def audio_disconnect_sysout():
	sysout_ports = jclient.get_ports("system", is_input=True, is_audio=True)
	for sop in sysout_ports:
		conports = jclient.get_all_connections(sop)
		for cp in conports:
			try:
				jclient.disconnect(cp, sop)
			except:
				pass


def get_layer_audio_out_ports(layer):
	aout_ports = []
	for p in layer.get_audio_out():
		if p == "system":
			aout_ports += ["system:playback_1", "system:playback_2"]
		elif p == "mixer":
			if layer.midi_chan >= 17:
				aout_ports += ["zynmixer:return_a", "zynmixer:return_b"]
			else:
				aout_ports += ["zynmixer:input_{:02d}a".format(layer.midi_chan + 1), "zynmixer:input_{:02d}b".format(layer.midi_chan + 1)]
		elif p == "mod-ui":
			aout_ports += ["zynmixer:input_moduia", "zynmixer:input_moduib"]
		else:
			aout_ports.append(p)
	return list(dict.fromkeys(aout_ports).keys()) 


def get_audio_input_ports(exclude_system_playback=False):
	res = OrderedDict()
	try:
		for aip in jclient.get_ports(is_input=True, is_audio=True, is_physical=False):
			parts = aip.name.split(':')
			client_name = parts[0]
			if client_name in ["jack_capture", "Headphones", "mod-monitor"] or client_name[:7] == "effect_":
				continue
			if client_name == "system" or client_name == "zynmixer":
				if exclude_system_playback:
					continue
				else:
					client_name = aip.name
			if client_name not in res:
				res[client_name] = [aip]
				#logger.debug("AUDIO INPUT PORT: {}".format(client_name))
			else:
				res[client_name].append(aip)
	except:
		pass
	return res


def get_audio_capture_ports():
	return jclient.get_ports("system", is_output=True, is_audio=True, is_physical=True)


def get_audio_playback_ports():
	ports = jclient.get_ports("zynmixer", is_input=True, is_audio=True, is_physical=False)
	return ports + jclient.get_ports("system", is_input=True, is_audio=True, is_physical=True)


def autoconnect(force=False):
	midi_autoconnect(force)
	audio_autoconnect(force)


def autoconnect_thread():
	global refresh_time, mididev_refresh_time, mididev_refresh_time_count
	while not exit_flag:
		try:
			# Run full autoconnect if pending (MIDI, audio or both)
			zynthian_gui_config.zyngui.zynautoconnect_do()
			# Run partial autoconnect for detecting new MIDI ports
			if mididev_refresh_time_count > mididev_refresh_time:
				midi_autoconnect(False)
		except Exception as err:
			logger.error("ZynAutoConnect ERROR: {}".format(err))

		sleep(refresh_time)
		mididev_refresh_time_count += refresh_time


def acquire_lock():
	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Waiting for lock, requested from '{}'...".format(format(calframe[1][3])))
	lock.acquire()
	#logger.debug("... lock acquired!!")


def release_lock():
	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Lock released from '{}'".format(calframe[1][3]))
	lock.release()


def start(rt=0.1):
	global refresh_time, exit_flag, jclient, thread, lock
	refresh_time = rt
	exit_flag = False

	try:
		jclient = jack.Client("Zynthian_autoconnect")
		jclient.set_xrun_callback(cb_jack_xrun)
		jclient.activate()
	except Exception as e:
		logger.error("ZynAutoConnect ERROR: Can't connect with Jack Audio Server ({})".format(e))

	# Create Lock object (Mutex) to avoid concurrence problems
	lock = Lock()

	# Initialize device mode cache table
	update_midi_in_dev_mode_all()

	# Start Autoconnect Thread
	thread = Thread(target=autoconnect_thread, args=())
	thread.daemon = True  # thread dies with the program
	thread.name = "autoconnect"
	thread.start()


def stop():
	global exit_flag
	exit_flag = True
	acquire_lock()
	audio_disconnect_sysout()
	release_lock()
	jclient.deactivate()


def is_running():
	global thread
	return thread.is_alive()


def cb_jack_xrun(delayed_usecs: float):
	logger.warning("Jack Audio XRUN! => delayed {}us".format(delayed_usecs))
	zynthian_gui_config.zyngui.status_info['xrun'] = True


def get_jackd_cpu_load():
	return jclient.cpu_load()


def get_jackd_samplerate():
	return jclient.samplerate


def get_jackd_blocksize():
	return jclient.blocksize

# ------------------------------------------------------------------------------
