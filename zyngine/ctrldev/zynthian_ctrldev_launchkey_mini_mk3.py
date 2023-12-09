#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey Mini MK3"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey Mini MK3
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchkey_mini_mk3(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

	dev_ids = ["Launchkey Mini MK3 MIDI 2"]

	PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
	STARTING_COLOUR = 123
	STOPPING_COLOUR = 120


	def init(self):
		# Enable session mode on launchkey
		self.shift = False
		lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
		self.refresh_zynpad_bank()


	def end(self):
		# Disable session mode on launchkey
		lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)


	def refresh_zynpad_bank(self):
		# Update pad status
		for row in range(2):
			too_big = row >= self.zynseq.col_in_bank
			for col in range(8):
				too_big |= col >= self.zynseq.col_in_bank
				if too_big:
					note = 96 + row * 16 + col
					lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
				else:
					pad = self.zynseq.col_in_bank * col + row
					state = self.zynseq.libseq.getPlayState(self.zynseq.bank, pad)
					mode = self.zynseq.libseq.getPlayMode(self.zynseq.bank, pad)
					self.update_pad(pad, state, mode)


	def update_pad(self, pad, state, mode):
		col, row = self.zynseq.get_xy_from_pad(pad)
		if row > 1:
			return
		note = 96 + row * 16 + col
		try:
			group = self.zynseq.libseq.getGroup(self.zynseq.bank, pad)
			if mode == 0 or group > 16:
				chan = 0
				vel = 0
			elif state == zynseq.SEQ_STOPPED:
				chan = 0
				vel = self.PAD_COLOURS[group]
			elif state == zynseq.SEQ_PLAYING:
				chan = 2
				vel = self.PAD_COLOURS[group]
			elif state == zynseq.SEQ_STOPPING:
				chan = 1
				vel = self.STOPPING_COLOUR
			elif state == zynseq.SEQ_STARTING:
				chan = 1
				vel = self.STARTING_COLOUR
			else:
				chan = 0
				vel = 0
		except Exception as e:
			chan = 0
			vel = 0
			#logging.warning(e)

		lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)


	def midi_event(self, ev):
		evtype = (ev & 0xF00000) >> 20
		cmd = (ev & 0xFF0000) >> 16
		val1 = (ev & 0xFF00) >> 8
		val2 = (ev & 0xFF)
		if evtype == 0x9:
			note = (ev >> 8) & 0x7F
			# Entered session mode so set pad LEDs => This shouldn't work because message size is fixed to 3 bytes!
			if ev == 0x90900C7F:
				self.refresh_zynpad_bank()
			else:
				# Toggle pad
				try:
					col = (note - 96) // 16
					row = (note - 96) % 16
					pad = row * self.zynseq.col_in_bank + col
					if pad < self.zynseq.seq_in_bank:
						self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
				except:
					pass
		elif evtype == 0xB:
			if val1 > 20 and val1 < 29:
				self.zynmixer.set_level(val1 - 21, val2 / 127.0)
			elif val1 == 0x6C:
				# SHIFT
				self.shift = val2 != 0
			elif val2 == 0:
				return True
			if val1 == 0x68:
				# UP
				self.state_manager.send_cuia("ARROW_UP")
			elif val1 == 0x69:
				# DOWN
				self.state_manager.send_cuia("ARROW_DOWN")
			elif val1 == 0x73:
				# PLAY
				if self.shift:
					self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
				else:
					self.state_manager.send_cuia("TOGGLE_AUDIO_PLAY")
			elif val1 == 0x75:
				# RECORD
				if self.shift:
					self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
				else:
					self.state_manager.send_cuia("TOGGLE_AUDIO_RECORD")
			elif val1 == 0x66:
				# TRACK RIGHT
				self.state_manager.send_cuia("ARROW_RIGHT")
			elif val1 == 0x67:
				# TRACK LEFT
				self.state_manager.send_cuia("ARROW_LEFT")
		elif evtype == 0xC:
			self.zynseq.select_bank(val1 + 1)

		return True

#------------------------------------------------------------------------------
