#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <riban@zynthian.org>
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

import sys
import tkinter
from PIL import Image, ImageTk
import os
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

#------------------------------------------------------------------------------
# Zynthian Widget Class for "zynaudioplayer"
#------------------------------------------------------------------------------

class zynthian_widget_audioplayer(zynthian_widget_base.zynthian_widget_base):


	def __init__(self):
		super().__init__()
		self.refreshing = False
		self.play_pos = 0.0
		self.filename = ""
		self.duration = 0.0
		self.samplerate = 44100
		self.bg_color = "000000"
		self.waveform_color = "6070B0"


	def create_gui(self):
		super().create_gui()

		self.loading_text = self.mon_canvas.create_text(
			int(self.width / 2),
			int(self.height / 2),
			anchor=tkinter.CENTER,
			font=(
				zynthian_gui_config.font_family,
				int(1.5 * zynthian_gui_config.font_size)
			),
			justify=tkinter.CENTER,
			fill=zynthian_gui_config.color_tx_off,
			text="Creating\nwaveform..."
		)
		
		self.waveform = self.mon_canvas.create_image(
			0,
			0,
			anchor=tkinter.NW,
			state=tkinter.HIDDEN
		)

		self.play_line = self.mon_canvas.create_line(
			0,
			0,
			0,
			self.height,
			fill=zynthian_gui_config.color_on
		)

		self.info_text = self.mon_canvas.create_text(
			self.width-int(0.5 * zynthian_gui_config.font_size),
			self.height,
			anchor = tkinter.SE,
			justify=tkinter.RIGHT,
			width=self.width,
			font=(zynthian_gui_config.font_family, int(1.5 * zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_panel_tx,
			text="00:00"
		)


	def refresh_gui(self):
		if self.refreshing:
			return
		self.refreshing = True
		try:
			pos = self.monitors["pos"]
			dur = self.monitors["duration"]
			if dur and self.play_pos != pos:
				self.play_pos = pos
				x =  int(pos / dur * self.width)
				self.mon_canvas.coords(
					self.play_line,
					x,
					0,
					x,
					self.height
				)
			if self.duration != dur:
				self.duration = dur
				self.mon_canvas.itemconfigure(self.info_text, text="{:02d}:{:02d}".format(int(dur / 60), int(dur % 60)), state=tkinter.NORMAL)
			if dur and self.filename != self.monitors["filename"]:
				self.mon_canvas.itemconfigure(self.waveform, state=tkinter.HIDDEN)
				self.mon_canvas.itemconfigure(self.loading_text, text="Creating\nwaveform...")
				waveform_png = "{}.png".format(self.monitors["filename"])
				self.filename = self.monitors["filename"]
				if not os.path.exists(waveform_png) or os.path.getmtime(self.filename) > os.path.getmtime(waveform_png):
					cmd = 'audiowaveform -i "{}" -o "{}" --split-channels -w {} -h {} --zoom auto --background-color {} --waveform-color {} --no-axis-labels > /dev/null 2>&1'.format(
						self.filename,
						waveform_png,
						self.width,
						self.height,
						self.bg_color,
						self.waveform_color
					)
					os.system(cmd)
				if os.path.exists(waveform_png):
					self.img=ImageTk.PhotoImage(file=waveform_png)
					self.mon_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
				else:
					self.mon_canvas.itemconfigure(self.loading_text, text="Cannot\ndisplay\nwaveform")

		except Exception as e:
			logging.error(e)
		
		self.refreshing = False



#------------------------------------------------------------------------------
