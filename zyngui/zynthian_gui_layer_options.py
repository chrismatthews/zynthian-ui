#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Layer Options Class
#
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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

import logging
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Layer Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer_options(zynthian_gui_selector):

	def __init__(self):
		self.reset()
		super().__init__('Option', True)


	def reset(self):
		self.index = 0
		self.layer_index = None
		self.layer = None
		self.audiofx_layers = None
		self.midifx_layers = None


	def setup(self, layer_index=None):
		if layer_index is not None:
			self.layer_index = layer_index

		if self.layer_index is None:
			self.layer_index = self.zyngui.screens['layer'].get_root_layer_index()

		if self.layer_index is not None:
			try:
				self.layer = self.zyngui.screens['layer'].get_root_layers()[self.layer_index]
				return True
			except Exception as e:
				self.layer = None
				logging.error("Bad layer index '{}'! => {}".format(self.layer_index, e))
		else:
			self.layer = None
			logging.error("No layer index!")

		return False


	def fill_list(self):
		self.list_data = []

		self.audiofx_layers = self.zyngui.screens['layer'].get_fxchain_layers(self.layer)

		self.midifx_layers = self.zyngui.screens['layer'].get_midichain_layers(self.layer)

		# Add root layer options
		if self.layer.midi_chan == 256:
			eng_options = {
				'audio_capture': False,
				'midi_capture': False,
				'indelible': True,
				'audio_rec': True,
				'audio_route': True,
				'midi_route': False,
				'midi_learn': True
			}
		else:
			eng_options = self.layer.engine.get_options()
			# MIDI-learn option is only shown when there is some "real" engine in the chain
			if self.layer.engine.type == "Audio Effect" and len(self.audiofx_layers) <= 1:
				eng_options['midi_learn'] = False
			else:
				eng_options['midi_learn'] = True

		if 'note_range' in eng_options and eng_options['note_range']:
			self.list_data.append((self.layer_note_range, None, "Note Range & Transpose"))

		if 'midi_capture' in eng_options and eng_options['midi_capture']:
			self.list_data.append((self.layer_midi_capture, None, "MIDI In"))

		if 'midi_route' in eng_options and eng_options['midi_route']:
			self.list_data.append((self.layer_midi_routing, None, "MIDI Out"))

		if 'midi_chan' in eng_options and eng_options['midi_chan']:
			self.list_data.append((self.layer_midi_chan, None, "MIDI Channel"))

		if 'clone' in eng_options and eng_options['clone']:
			self.list_data.append((self.layer_clone, None, "Clone MIDI to..."))

		if 'midi_learn' in eng_options and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			self.list_data.append((self.midi_learn, None, "MIDI Learn"))

		if self.layer.engine.type != 'MIDI Tool':
			self.list_data.append((self.audio_options, None, "Audio Options..."))

		if 'audio_capture' in eng_options and eng_options['audio_capture']:
			self.list_data.append((self.layer_audio_capture, None, "Audio In"))

		if 'audio_route' in eng_options and eng_options['audio_route']:
			self.list_data.append((self.layer_audio_routing, None, "Audio Out"))

		if 'audio_rec' in eng_options and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			if self.zyngui.audio_recorder.get_status():
				self.list_data.append((self.toggle_recording, None, "■ Stop Audio Recording"))
			else:
				self.list_data.append((self.toggle_recording, None, "⬤ Start Audio Recording"))

		self.list_data.append((None, None, "> Chain"))

		if self.layer.engine.type in ('MIDI Synth', 'MIDI Tool'):
			# Add MIDI-FX options
			self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

		self.list_data += self.generate_chaintree_menu()

		if self.layer.engine.type != 'MIDI Tool':
			# Add Audio-FX options
			self.list_data.append((self.audiofx_add, None, "Add Audio-FX"))

		if self.layer.midi_chan == 256:
			if self.audiofx_layers:
				self.list_data.append((self.remove_all_audiofx, None, "Remove All Audio-FXs"))
#		elif self.layer.engine.type == 'MIDI Tool' and len(self.midifx_layers) > 1:
#			self.list_data.append((self.remove_all, None, "Remove..."))
		elif self.layer.engine.type != 'MIDI Tool' and len(self.midifx_layers) + len(self.audiofx_layers) > 0:
			self.list_data.append((self.remove_all, None, "Remove..."))
		else:
			self.list_data.append((self.remove_chain, None, "Remove Chain"))

		super().fill_list()


	# Generate chain tree menu
	def generate_chaintree_menu(self):
		res = []
		indent = 0
		front = True
		prev_layer = None
		for layer in list(dict.fromkeys(self.midifx_layers + [self.layer] + self.audiofx_layers)):
			name = layer.engine.get_name(layer)
			if prev_layer and layer.engine.type != prev_layer.engine.type:
				prev_layer = None
			if layer.engine.type == "MIDI Tool":
				flowchar = "╰─ "
				if layer == prev_layer:
					# Must be at end of MIDI only chain
					break
				if not layer.is_parallel_midi_routed(prev_layer):
					if not front:
						indent += 1
				else:
					last_entry = list(res.pop())
					last_entry[2] = last_entry[2].replace('╰', '├')
					res.append(tuple(last_entry))
			elif layer.engine.type == "Audio Effect":
				flowchar = "┗━ "
				if layer.engine.nickname == "AI":
					continue
				if not layer.is_parallel_audio_routed(prev_layer):
					if not front:
						indent += 1
				else:
					last_entry = list(res.pop())
					last_entry[2] = last_entry[2].replace('┗', '┣')
					res.append(tuple(last_entry))
			else:
				flowchar = "╰━ "
				if not front:
					indent += 1
			res.append((self.sublayer_options, layer, "  " * indent + flowchar + name))
			prev_layer = layer
			front = False
		return res


	def refresh_signal(self, sname):
		if sname=="AUDIO_RECORD":
			self.fill_list()


	def search_fx_index(self, sl):
		for i,row in enumerate(self.list_data):
			if row[1]==sl:
				return i
		return 0


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def build_view(self):
		if self.layer is None:
			self.setup()

		if self.layer is not None and self.layer in self.zyngui.screens['layer'].root_layers:
			super().build_view()
			if self.index >= len(self.list_data):
				self.index = len(self.list_data)-1
		else:
			self.zyngui.close_screen()


	def select_action(self, i, t='S'):
		self.index = i
		if self.list_data[i][0] is None:
			pass
		elif self.list_data[i][1] is None:
			self.list_data[i][0]()
		else:
			self.list_data[i][0](self.list_data[i][1], t)


	def back_action(self):
		if self.layer.engine.type in ("Audio Effect", "MIDI Tool") and len(self.midifx_layers) + len(self.audiofx_layers) == 0:
			self.zyngui.show_screen_reset('audio_mixer')
			return True
		return False


	def arrow_right(self):
		next_index = self.layer_index + 1
		if next_index < self.zyngui.screens['layer'].get_num_root_layers():
			self.setup(next_index)
			self.set_select_path()
			self.fill_list()


	def arrow_left(self):
		prev_index = self.layer_index - 1
		if prev_index >= 0:
			self.setup(prev_index)
			self.set_select_path()
			self.fill_list()


	def sublayer_options(self, sublayer, t='S'):
		self.zyngui.screens['sublayer_options'].setup(self.layer, sublayer)
		self.zyngui.show_screen("sublayer_options")


	def layer_midi_chan(self):
		chan_list = self.zyngui.screens['layer'].get_free_midi_chans() + [self.layer.midi_chan]
		chan_list.sort()
		self.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan, chan_list)
		self.zyngui.show_screen('midi_chan')


	def layer_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		self.zyngui.show_screen('midi_chan')


	def layer_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.layer.midi_chan)
		self.zyngui.show_screen('midi_key_range')


	def layer_transpose(self):
		self.zyngui.show_screen('transpose')


	def midi_learn(self):
		options = OrderedDict()
		options['Enter MIDI-learn'] = "enter"
		options['Clean MIDI-learn'] = "clean"
		self.zyngui.screens['option'].config("MIDI-learn", options, self.midi_learn_menu_cb)
		self.zyngui.show_screen('option')


	def midi_learn_menu_cb(self, options, params):
		if params == 'enter':
			if self.zyngui.current_screen != "control":
				self.zyngui.show_screen("control")
			self.zyngui.enter_midi_learn()
		elif params == 'clean':
			if self.layer.midi_chan == 256:
				chain_label = "MAIN"
			else:
				chain_label = "CH#{}".format(self.layer.midi_chan + 1)
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL controls in ALL engines at {}?".format(chain_label), self.zyngui.screens['layer'].midi_unlearn, self.layer)


	def layer_midi_routing(self):
		self.zyngui.screens['midi_out'].set_layer(self.layer)
		self.zyngui.show_screen('midi_out')


	def layer_audio_routing(self):
		self.zyngui.screens['audio_out'].set_layer(self.layer)
		self.zyngui.show_screen('audio_out')


	def audio_options(self):
		options = OrderedDict()
		if self.zyngui.zynmixer.get_mono(self.layer.midi_chan):
			options['\u2612 Mono'] = 'mono'
		else:
			options['\u2610 Mono'] = 'mono'
		if self.zyngui.zynmixer.get_phase(self.layer.midi_chan):
			options['\u2612 Phase reverse'] = 'phase'
		else:
			options['\u2610 Phase reverse'] = 'phase'

		self.zyngui.screens['option'].config("Audio options", options, self.audio_menu_cb)
		self.zyngui.show_screen('option')


	def audio_menu_cb(self, options, params):
		if params == 'mono':
			self.zyngui.zynmixer.toggle_mono(self.layer.midi_chan)
		elif params == 'phase':
			self.zyngui.zynmixer.toggle_phase(self.layer.midi_chan)
		self.audio_options()


	def layer_audio_capture(self):
		self.zyngui.screens['audio_in'].set_layer(self.layer)
		self.zyngui.show_screen('audio_in')


	def layer_midi_capture(self):
		self.zyngui.screens['midi_in'].set_layer(self.layer)
		self.zyngui.show_screen('midi_in')


	def toggle_recording(self):
		self.zyngui.audio_recorder.toggle_recording()
		self.fill_list()


	# Remove submenu

	def remove_all(self):
		options = OrderedDict()
		if self.midifx_layers:
			options['Remove All MIDI-FXs'] = "midifx"
		if self.audiofx_layers:
			options['Remove All Audio-FXs'] = "audiofx"
		if self.layer.midi_chan != 256:
			options['Remove Chain'] = "chain"
		self.zyngui.screens['option'].config("Remove...", options, self.remove_all_cb)
		self.zyngui.show_screen('option')


	def remove_all_cb(self, options, params):
		if params == 'midifx':
			self.remove_all_midifx()
		elif params == 'audiofx':
			self.remove_all_audiofx()
		elif params == 'chain':
			self.remove_chain()


	def remove_chain(self, params=None):
		self.zyngui.show_confirm("Do you really want to remove this chain?", self.chain_remove_confirmed)


	def chain_remove_confirmed(self, params=None):
		self.zyngui.screens['layer'].remove_root_layer(self.layer_index)
		self.zyngui.show_screen_reset('audio_mixer')


	# FX-Chain management

	def audiofx_add(self):
		self.zyngui.screens['layer'].add_fxchain_layer(self.layer)


	def remove_all_audiofx(self):
		self.zyngui.show_confirm("Do you really want to remove all audio effects from this chain?", self.audiofx_reset_confirmed)


	def audiofx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.audiofx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		if self.layer in self.zyngui.screens['layer'].root_layers:
			self.build_view()
			self.show()
		else:
			self.zyngui.close_screen()


	# MIDI-Chain management

	def midifx_add(self):
		self.zyngui.screens['layer'].add_midichain_layer(self.layer.midi_chan)


	def remove_all_midifx(self):
		self.zyngui.show_confirm("Do you really want to remove all MIDI effects from this chain?", self.midifx_reset_confirmed)


	def midifx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.midifx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		if self.layer in self.zyngui.screens['layer'].root_layers:
			self.build_view()
			self.show()
		else:
			self.zyngui.close_screen()


	# Select Path

	def set_select_path(self):
		if self.layer:
			if self.layer.midi_chan is None or self.layer.midi_chan<16:
				self.select_path.set("{} > Chain Options".format(self.layer.get_basepath()))
			else:
				self.select_path.set("Main > Chain Options")
		else:
			self.select_path.set("Chain Options")


#------------------------------------------------------------------------------
