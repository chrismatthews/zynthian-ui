# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audioplayer)
#
# zynthian_engine implementation for audio player
#
# Copyright (C) 2021-2023 Brian Walton <riban@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import os
import logging
from glob import glob
from collections import OrderedDict

from zynlibs.zynaudioplayer import zynaudioplayer
from . import zynthian_engine
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Audio Player Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_audioplayer(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None, jackname=None):
		super().__init__(zyngui)
		self.name = "AudioPlayer"
		self.nickname = "AP"
		self.type = "MIDI Synth"
		self.options['replace'] = False

		if jackname:
			self.jackname = jackname
		else:
			self.jackname = self.get_next_jackname("audioplayer")

		self.file_exts = []
		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"

		# MIDI Controllers
		self._ctrls = [
			['gain', None, 1.0, 2.0],
			['record', None, 'stopped', ['stopped', 'recording']],
			['loop', None, 'one-shot', ['one-shot', 'looping']],
			['transport', None, 'stopped', ['stopped', 'playing']],
			['position', None, 0.0, 0.0],
			['left track', None, 0, [['mixdown'], [0]]],
			['right track', None, 0, [['mixdown'], [0]]],
			['loop start', None, 0.0, 0.0],
			['loop end', None, 0.0, 0.0],
			['crop start', None, 0.0, 0.0],
			['crop end', None, 0.0, 0.0],
			['attack', None, 0.1, 20.0],
			['decay', None, 0.1, 20.0],
			['sustain', None, 0.8, 1.0],
			['release', None, 0.1, 20.0],
			['zoom', None, 1, ["x1"],[1]],
			['info', None, 1, ["None", "Duration", "Position", "Remaining", "Loop length", "Samplerate", "CODEC", "Filename"]],
			['bend range', None, 2, 24],
			['view offset', None, 0, 1],
			['amp zoom', None, 1.0, 10.0]
		]

		# Controller Screens
		self._ctrl_screens = [
			['main', ['record', 'gain']],
		]

		self.monitors_dict = {}
		self.start()
		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		self.player = zynaudioplayer.zynaudioplayer(self.jackname)
		self.jackname = self.player.get_jack_client_name()
		self.file_exts = self.get_file_exts()
		self.player.set_control_cb(self.control_cb)


	def stop(self):
		try:
			self.player.stop()
			self.player = None
		except Exception as e:
			logging.error("Failed to close audio player: %s", e)


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		handle = self.player.add_player()
		if handle == 0:
			return
		self.layers.append(layer)
		layer.handle = handle
		layer.jackname = self.jackname
		layer.jackname = "{}:out_{:02d}(a|b)".format(self.jackname, self.player.get_index(handle))
		self.set_midi_chan(layer)
		self.monitors_dict[layer.handle] = OrderedDict()
		self.monitors_dict[layer.handle]["filename"] = ""
		self.monitors_dict[layer.handle]["info"] = 0
		self.monitors_dict[layer.handle]['frames'] = 0
		self.monitors_dict[layer.handle]['channels'] = 0
		self.monitors_dict[layer.handle]['samplerate'] = 44100
		self.monitors_dict[layer.handle]['codec'] = "UNKNOWN"


	def del_layer(self, layer):
		self.player.remove_player(layer.handle)
		super().del_layer(layer)


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.player.set_midi_chan(layer.handle, layer.midi_chan)


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		banks = [[self.my_data_dir + "/capture", None, "Internal", None]]

		walk = next(os.walk(self.my_data_dir + "/capture"))
		walk[1].sort()
		for dir in walk[1]:
			for ext in self.file_exts:
				if glob(walk[0] + "/" + dir + "/*." + ext):
					banks.append([walk[0] + "/" + dir, None, "  " + dir, None])
					break

		for exd in zynthian_gui_config.get_external_storage_dirs(self.ex_data_dir):
			dname = os.path.basename(exd)
			for ext in self.file_exts:
				if glob(exd + "/*." + ext) or glob(exd + "/*/*." + ext):
					banks.append([exd, None, "USB> {}".format(dname), None])
					walk = next(os.walk(exd))
					walk[1].sort()
					for dir in walk[1]:
						for ext in self.file_exts:
							if glob(walk[0] + "/" + dir + "/*." + ext):
								banks.append([walk[0] + "/" + dir, None, "  " + dir, None])
								break
					break

		return banks


	def set_bank(self, layer, bank):
		return True

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_file_exts(self):
		file_exts = self.player.get_supported_codecs()
		logging.info("Supported Codecs: {}".format(file_exts))
		exts_upper = []
		for ext in file_exts:
			exts_upper.append(ext.upper())
		file_exts += exts_upper
		return file_exts


	def get_preset_list(self, bank):
		presets = []
		for ext in self.file_exts:
			presets += self.get_filelist(bank[0], ext)
		for preset in presets:
			fparts = os.path.splitext(preset[4])
			duration = self.player.get_file_duration(preset[0])
			preset.append("{} ({:02d}:{:02d})".format(fparts[1], int(duration/60), round(duration)%60))
		return presets


	def set_preset(self, layer, preset, preload=False):
		if self.player.get_filename(layer.handle) == preset[0] and self.player.get_file_duration(preset[0]) == self.player.get_duration(layer.handle):
			return False

		good_file = self.player.load(layer.handle, preset[0])
		self.monitors_dict[layer.handle]['filename'] = self.player.get_filename(layer.handle)
		self.monitors_dict[layer.handle]['frames'] = self.player.get_frames(layer.handle)
		self.monitors_dict[layer.handle]['channels'] = self.player.get_frames(layer.handle)
		self.monitors_dict[layer.handle]['samplerate'] = self.player.get_samplerate(layer.handle)
		self.monitors_dict[layer.handle]['codec'] = self.player.get_codec(layer.handle)

		dur = self.player.get_duration(layer.handle)
		self.player.set_position(layer.handle, 0)
		if self.player.is_loop(layer.handle):
			loop = 'looping'
		else:
			loop = 'one-shot'
		logging.debug("Loading Audio Track '{}' in player {}".format(preset[0], layer.handle))
		if self.player.get_playback_state(layer.handle):
			transport = 'playing'
		else:
			transport = 'stopped'
		if self.zyngui.audio_recorder.get_status():
			record = 'recording'
		else:
			record = 'stopped'
		gain = self.player.get_gain(layer.handle)
		bend_range = self.player.get_pitchbend_range(layer.handle)
		attack = self.player.get_attack(layer.handle)
		decay = self.player.get_decay(layer.handle)
		sustain = self.player.get_sustain(layer.handle)
		release = self.player.get_release(layer.handle)
		default_a = 0
		default_b = 0
		track_labels = ['mixdown']
		track_values = [-1]
		zoom_labels = ['x1']
		zoom_values = [1]
		z = 1
		while z < dur * 250:
			z *= 2
			zoom_labels.append(f"x{z}")
			zoom_values.append(z)
		if dur:
			channels = self.player.get_channels(layer.handle)
			if channels > 2:
				default_a = -1
				default_b = -1
			elif channels > 1:
				default_b = 1
			for track in range(channels):
				track_labels.append('{}'.format(track + 1))
				track_values.append(track)
			self._ctrl_screens = [
				['main', ['record', 'transport', 'position', 'gain']],
				['crop', ['crop start', 'crop end', 'position', 'zoom']],
				['loop', ['loop start', 'loop end', 'loop', 'zoom']],
				['config', ['left track', 'right track', 'bend range', 'sustain pedal']],
				['info', ['info', 'zoom range', 'amp zoom', 'view offset']]
			]
			if layer.handle == self.zyngui.audio_player.handle:
				self._ctrl_screens[3][1][2] = None
				self._ctrl_screens[3][1][3] = None
			else:
				self._ctrl_screens.insert(-2, ['envelope', ['attack', 'decay', 'sustain', 'release']])

		else:
			self._ctrl_screens = [
				['main', ['record', 'gain']],
			]

		self._ctrls = [
			['gain', None, gain, 2.0],
			['record', None, record, ['stopped', 'recording']],
			['loop', None, loop, ['one-shot', 'looping']],
			['transport', None, transport, ['stopped', 'playing']],
			['position', None, 0.0, dur],
			['left track', None, default_a, [track_labels, track_values]],
			['right track', None, default_b, [track_labels, track_values]],
			['loop start', None, 0.0, dur],
			['loop end', None, dur, dur],
			['crop start', None, 0.0, dur],
			['crop end', None, dur, dur],
			['zoom', None, 1, [zoom_labels, zoom_values]],
			['zoom range', None, 0, ["User", "File", "Crop", "Loop"]],
			['info', None, 1, ["None", "Duration", "Position", "Remaining", "Loop length", "Samplerate", "CODEC", "Filename"]],
			['view offset', None, 0, dur],
			['amp zoom', None, 1.0, 4.0],
			['sustain pedal', 64, 'off', ['off', 'on']],
			['bend range', None, bend_range, 24],
			['attack', None, attack, 20.0],
			['decay', None, decay, 20.0],
			['sustain', None, sustain, 1.0],
			['release', None, release, 20.0]
		]

		layer.refresh_controllers()
		self.player.set_track_a(layer.handle, default_a)
		self.player.set_track_b(layer.handle, default_b)

		return True


	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
			os.remove("{}.png".format(preset[0]))
		except Exception as e:
			logging.debug(e)


	def rename_preset(self, bank, preset, new_preset_name):
		src_ext = None
		dest_ext = None
		for ext in self.file_exts:
			if preset[0].endswith(ext):
				src_ext = ext
			if new_preset_name.endswith(ext):
				dest_ext = ext
			if src_ext and dest_ext:
				break
		if src_ext != dest_ext:
			new_preset_name += "." + src_ext
		try:
			os.rename(preset[0], "{}/{}".format(bank[0], new_preset_name))
		except Exception as e:
			logging.debug(e)

		
	def is_preset_user(self, preset):
		return True


	def load_latest(self, layer):
		bank_dirs = [os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"]
		bank_dirs += zynthian_gui_config.get_external_storage_dirs(os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root"))

		wav_fpaths = []
		for bank_dir in bank_dirs:
			wav_fpaths += glob(f"{bank_dir}/*.wav")

		if len(wav_fpaths) > 0:
			latest_fpath = max(wav_fpaths, key=os.path.getctime)
			bank_fpath = os.path.dirname(latest_fpath)
			layer.load_bank_list()
			layer.set_bank_by_id(bank_fpath)
			layer.load_preset_list()
			layer.set_preset_by_id(latest_fpath)


	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		ctrls = super().get_controllers_dict(layer)
		for zctrl in ctrls.values():
			zctrl.handle = layer.handle
		return ctrls


	def control_cb(self, handle, id, value):
		try:
			for layer in self.layers:
				if layer.handle == handle:
					ctrl_dict = layer.controllers_dict
					if id == 1:
						if value:
							ctrl_dict['transport'].set_value("playing", False)
							layer.status = "\uf04b"
						else:
							ctrl_dict['transport'].set_value("stopped", False)
							layer.status = ""
					elif id == 2:
						ctrl_dict['position'].set_value(value, False)
					elif id == 3:
						ctrl_dict['gain'].set_value(value, False)
					elif id == 4:
						ctrl_dict['loop'].set_value(int(value) * 64, False)
					elif id == 5:
						ctrl_dict['left track'].set_value(int(value), False)
					elif id == 6:
						ctrl_dict['right track'].set_value(int(value), False)
					elif id == 11:
						ctrl_dict['loop start'].set_value(value, False)
					elif id == 12:
						ctrl_dict['loop end'].set_value(value, False)
					elif id == 13:
						ctrl_dict['crop start'].set_value(value, False)
					elif id == 14:
						ctrl_dict['crop end'].set_value(value, False)
					elif id == 15:
						ctrl_dict['sustain pedal'].set_value(value, False)
					elif id == 16:
						ctrl_dict['attack'].set_value(value, False)
					elif id == 17:
						ctrl_dict['decay'].set_value(value, False)
					elif id == 18:
						ctrl_dict['sustain'].set_value(value, False)
					elif id == 19:
						ctrl_dict['release'].set_value(value, False)
					break
		except Exception as e:
			logging.error(e)


	def send_controller_value(self, zctrl):
		handle = zctrl.handle
		if zctrl.symbol == "position":
			self.player.set_position(handle, zctrl.value)
			self.monitors_dict[handle]['offset'] = None
		elif zctrl.symbol == "gain":
			self.player.set_gain(handle, zctrl.value)
		elif zctrl.symbol == "loop":
			self.player.enable_loop(handle, zctrl.value)
		elif zctrl.symbol == "transport":
			if zctrl.value > 63:
				self.player.start_playback(handle)
			else:
				self.player.stop_playback(handle)
		elif zctrl.symbol == "left track":
			self.player.set_track_a(handle, zctrl.value)
		elif zctrl.symbol == "right track":
			self.player.set_track_b(handle, zctrl.value)
		elif zctrl.symbol == "record":
			if zctrl.value:
				self.zyngui.cuia_start_audio_record()
			else:
				self.zyngui.cuia_stop_audio_record()
		elif zctrl.symbol == "loop start":
			self.player.set_loop_start(handle, zctrl.value)
		elif zctrl.symbol == "loop end":
			self.player.set_loop_end(handle, zctrl.value)
		elif zctrl.symbol == "crop start":
			self.player.set_crop_start(handle, zctrl.value)
		elif zctrl.symbol == "crop end":
			self.player.set_crop_end(handle, zctrl.value)
		elif zctrl.symbol == "bend range":
			self.player.set_pitchbend_range(handle, zctrl.value)
		elif zctrl.symbol == "sustain pedal":
			self.player.set_damper(handle, zctrl.value)
		elif zctrl.symbol == "zoom":
			self.monitors_dict[handle]['zoom'] = zctrl.value
			for layer in self.layers:
				if layer.handle == handle:
					layer.controllers_dict['zoom range'].set_value(0)
					pos_zctrl = layer.controllers_dict['position']
					pos_zctrl.nudge_factor = pos_zctrl.value_max / 400 / zctrl.value
					layer.controllers_dict['loop start'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['loop end'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['crop start'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['crop end'].nudge_factor = pos_zctrl.nudge_factor
					self.monitors_dict[handle]['offset'] = None
					return
		elif zctrl.symbol == "zoom range":
			for layer in self.layers:
				if layer.handle == handle:
					if zctrl.value == 1:
						# Show whole file
						layer.controllers_dict['zoom'].set_value(1, False)
						layer.controllers_dict['view offset'].set_value(0)
						range = self.player.get_duration(handle)
					elif zctrl.value == 2:
						# Show cropped region
						start = self.player.get_crop_start(handle)
						range = self.player.get_crop_end(handle) - start
						layer.controllers_dict['view offset'].set_value(start)
						layer.controllers_dict['zoom'].set_value(self.player.get_duration(handle) / range, False)
					elif zctrl.value == 3:
						# Show loop region
						start = self.player.get_loop_start(handle)
						range = self.player.get_loop_end(handle) - start
						layer.controllers_dict['view offset'].set_value(start)
						layer.controllers_dict['zoom'].set_value(self.player.get_duration(handle) / range, False)

		elif zctrl.symbol == "info":
			self.monitors_dict[handle]['info'] = zctrl.value
		elif zctrl.symbol == "attack":
			self.player.set_attack(handle, zctrl.value)
		elif zctrl.symbol == "decay":
			self.player.set_decay(handle, zctrl.value)
		elif zctrl.symbol == "sustain":
			self.player.set_sustain(handle, zctrl.value)
		elif zctrl.symbol == "release":
			self.player.set_release(handle, zctrl.value)


	def get_monitors_dict(self, handle):
		return self.monitors_dict[handle]


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
