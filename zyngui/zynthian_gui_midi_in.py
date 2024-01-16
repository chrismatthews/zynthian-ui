#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-In Selector Class
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI-In Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_in(zynthian_gui_selector):

	def __init__(self):
		self.root_layer = None
		super().__init__('MIDI In', True)


	def set_layer(self, layer):
		try:
			self.root_layer = self.zyngui.screens['layer'].get_midichain_root(layer)
		except:
			self.root_layer = None


	def fill_list(self):
		self.list_data = []

		def append_device(i, devname):
			# Check if captured by device manager
			if self.zyngui.ctrldev_manager.get_device_driver(i+1):
				self.list_data.append((i, -1, "\u2610 ----- - " + devname))
			else:
				# Get mode: ACTI/OMNI/MULTI
				mode = zynautoconnect.get_midi_in_dev_mode(i)
				# Get routing info: Device enabled/disabled for this chain
				if lib_zyncore.zmop_get_route_from(self.root_layer.midi_chan, i):
					self.list_data.append((i, 0, "\u2612 " + mode + " - " + devname))
				else:
					self.list_data.append((i, 1, "\u2610 " + mode + " - " + devname))

		if self.root_layer:
			# Connected device ports
			for i in range(zynautoconnect.max_num_devs):
				dev_id = zynautoconnect.devices_in[i]
				if dev_id:
					append_device(i, dev_id.replace("_", " "))
			# Hardcoded ports
			append_device(16, "Network MIDI-IN")

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		self.highlight()


	# Highlight current engine assigned outputs ...
	def highlight(self):
		for i in range(len(self.list_data)):
			if self.list_data[i][1] < 0:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_tx_off})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i, t='S'):
		dev_i = self.list_data[i][0]
		# Ignore if captured by device manager
		if self.list_data[i][1] < 0:
			return
		# Route/Unroute
		elif t == 'S':
			lib_zyncore.zmop_set_route_from(self.root_layer.midi_chan, dev_i, self.list_data[i][1])
		# Change mode
		elif t == 'B':
			lib_zyncore.zmip_rotate_flags_active_omni_chan(dev_i)
			zynautoconnect.update_midi_in_dev_mode(dev_i)
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Capture MIDI from ...")

#------------------------------------------------------------------------------
