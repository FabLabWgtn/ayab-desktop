# -*- coding: utf-8 -*-
# This file is part of AYAB.
#
#    AYAB is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    AYAB is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with AYAB.  If not, see <http://www.gnu.org/licenses/>.
#
#    Copyright 2013-2020 Christian Obersteiner, Andreas Müller,
#    Christian Gerbrandt
#    https://github.com/AllYarnsAreBeautiful/ayab-desktop

from bitarray import bitarray
import numpy as np

from .options import Alignment
from .mode import Mode, ModeFunc

from ayab.machine import Machine


class Pattern(object):
    FLANKING_NEEDLES = True

    def __init__(self, image, machine, options):
        self.machine = options.machine

        self.__pattern = image

        self.__num_colors = options.num_colors

        self.start_row = options.start_row
        self.mode = options.mode
        self.inf_repeat = options.inf_repeat
        self.continuous_reporting = options.continuous_reporting

        self.__alignment = Alignment.CENTER
        self.__pat_start_needle = -1
        self.__pat_end_needle = -1
        self.__knit_start_needle = 0
        self.__knit_end_needle = machine.width
        self.__update_pattern_data()

    def __update_pattern_data(self):
        self.__pat_width = self.__pattern.width
        self.__pat_height = self.__pattern.height
        self.__convert()
        self.__func_selector()

        self.len_pat_expanded = self.pat_height * self.num_colors
        self.passes_per_row = self.mode.row_multiplier(self.num_colors)
        self.start_needle = max(0, self.__pat_start_needle)
        self.start_needle = max(0, self.__pat_start_needle)
        self.end_needle = min(
           self.__pat_width + self.__pat_start_needle,
           self.machine.width)
        self.start_pixel = self.start_needle - self.__pat_start_needle
        self.end_pixel = self.end_needle - self.__pat_start_needle
        if self.FLANKING_NEEDLES:
           self.midline = self.__knit_end_needle - self.machine.width // 2
        else:
           self.midline = self.end_needle - self.machine.width // 2


        self.__compile()
        self.__calc_pat_start_end_needles()

    def __convert(self):
        num_colors = self.__num_colors
        pat_width = self.__pat_width
        pat_height = self.__pat_height

        self.__pattern_intern = \
            [[0 for i in range(self.__pat_width)]
                for j in range(self.__pat_height)]
        self.__pattern_colors = \
            [[0 for i in range(self.__num_colors)]
                for j in range(self.__pat_height)]  # unused
        self.__pattern_expanded = \
            [bitarray([False] * self.__pat_width)
                for j in range(self.__num_colors * self.__pat_height)]

        # Limit number of colors in pattern
        # self.__pattern = self.__pattern.quantize(num_colors, dither=None)
        self.__pattern = self.__pattern.quantize(self.__num_colors)

        # Order colors most-frequent first
        # NB previously they were ordered lightest-first
        histogram = self.__pattern.histogram()
        dest_map = list(np.argsort(histogram[0:self.__num_colors]))
        dest_map.reverse()
        self.__pattern = self.__pattern.remap_palette(dest_map)

        # reduce number of colors if necessary
        actual_num_colors = sum(
            map(lambda x: x > 0, self.__pattern.histogram()))
        if actual_num_colors < self.__num_colors:
            # TODO: issue warning if number of colors is less than expected
            # TODO: reduce number of colors
            # self.__num_colors = num_colors = actual_num_colors
            # TODO: reduce number of colors in configuration box
            pass

        # get palette
        rgb = self.__pattern.getpalette()[slice(0, 3 * self.__num_colors)]
        col_array = np.reshape(rgb, (self.__num_colors, 3))
        self.palette = list(map(self.array2rgb, col_array))

        # Make internal representations of pattern
        for row in range(self.__pat_height):
            for col in range(self.__pat_width):
                pxl = self.__pattern.getpixel((col, row))
                for color in range(self.__num_colors):
                    if pxl == color:
                        # color map
                        self.__pattern_intern[row][col] = color
                        # amount of bits per color per line
                        self.__pattern_colors[row][color] += 1
                        # colors separated per line
                        self.__pattern_expanded[(self.__num_colors * row) +
                                                color][col] = True

    def __compile(self):
        print("pattern compile")
        self.__line_data = []
        line_number = 0
        last_line = False
        line_data = []

        while not last_line:
                    # get data for next line of knitting

            color, row_index, pat_row, blank_line, last_line = self.mode_func(self, line_number)
            bits = self.select_needles_API6(color, row_index, blank_line)

            if (self.mode.optimize() and len(self.__line_data)>0 and sum(bits)==0 and sum(self.__line_data[-1]["bits"])==0 and color == self.__line_data[-1]["color"]):
                self.__line_data.pop()
            else:
                self.__line_data.append({
                    "color": color,
                    "row_index": row_index,
                    "pat_row": pat_row,
                    "blank_line": blank_line,
                    "last_line": last_line,
                    "bits": bits
                })
            line_number += 1
        print(self.__line_data)

    def line_data(self, line_number):
        line_data = self.__line_data[line_number]
        return line_data["color"], line_data["row_index"], line_data["pat_row"], line_data["blank_line"], line_data["last_line"], line_data["bits"]

    def __func_selector(self):
        """
        Method selecting the function that decides which line of data to send
        according to the knitting mode and number of colors.

        @author Tom Price
        @date   June 2020
        """
        if not self.mode.good_ncolors(self.num_colors):
            self.logger.error("Wrong number of colours for the knitting mode")
            return False
        # else
        func_name = self.mode.knit_func(self.num_colors)
        if not hasattr(ModeFunc, func_name):
            self.logger.error(
                "Unrecognized value returned from Mode.knit_func()")
            return False
        # else
        self.mode_func = getattr(ModeFunc, func_name)
        return True

    def select_needles_API6(self, color, row_index, blank_line):
        bits = bitarray([False] * self.machine.width, endian="little")

        # select needles flanking the pattern
        # if necessary to knit the background color
        if self.mode.flanking_needles(color, self.num_colors):
            bits[0:self.start_needle] = True
            bits[self.end_needle:self.machine.width] = True

        if not blank_line:
            bits[self.start_needle:self.end_needle] = (
                self.__pattern_expanded
            )[row_index][self.start_pixel:self.end_pixel]

        return bits

    def __calc_pat_start_end_needles(self):
        # the sequence of needles is printed in right to left by default
        # so the needle count starts at 0 on the right hand side
        if self.__alignment == Alignment.CENTER:
            needle_width = self.__knit_end_needle - self.__knit_start_needle
            self.__pat_start_needle = \
                self.__knit_start_needle + (needle_width - self.pat_width + 1) // 2
            self.__pat_end_needle = self.__pat_start_needle + self.__pat_width
        elif self.__alignment == Alignment.RIGHT:
            self.__pat_start_needle = self.__knit_start_needle
            self.__pat_end_needle = self.__pat_start_needle + self.__pat_width
        elif self.__alignment == Alignment.LEFT:
            self.__pat_end_needle = self.__knit_end_needle
            self.__pat_start_needle = self.__pat_end_needle - self.__pat_width
        else:
            return False
        return True

    def set_knit_needles(self, knit_start, knit_stop, machine):
        """
        set the start and stop needle
        """
        if knit_start < knit_stop and knit_start >= 0 and knit_stop < machine.width:
            self.__knit_start_needle = knit_start
            self.__knit_end_needle = knit_stop + 1
        self.__update_pattern_data()

    @property
    def num_colors(self):
        return self.__num_colors

    @num_colors.setter
    def num_colors(self, num_colors):
        """
        sets the number of colors used for knitting
        """
        # TODO use preferences or other options to set maximum number of colors
        if num_colors > 1 and num_colors < 7:
            self.__num_colors = num_colors
            self.__update_pattern_data()

    @property
    def alignment(self):
        return self.__alignment

    @alignment.setter
    def alignment(self, alignment):
        """
        set the position of the pattern
        """
        self.__alignment = alignment
        self.__update_pattern_data()

    @property
    def pat_start_needle(self):
        return self.__pat_start_needle

    @property
    def pat_end_needle(self):
        return self.__pat_end_needle

    @property
    def knit_start_needle(self):
        return self.__knit_start_needle

    @property
    def knit_end_needle(self):
        return self.__knit_end_needle

    @property
    def pat_height(self):
        return self.__pat_height

    @property
    def pat_width(self):
        return self.__pat_width

    @property
    def pattern_expanded(self):
        return self.__pattern_expanded

    def array2rgb(self, a):
        return (a[0] & 0xFF) * 0x10000 + (a[1] & 0xFF) * 0x100 + (a[2] & 0xFF)
