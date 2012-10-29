#!/usr/bin/env python
# -*- coding: utf-8 -*-

#Copyright (c) 2011 Walter Bender

# Port To GTK3:
# Ignacio Rodriguez <ignaciorodriguez@sugarlabs.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA


import os


class SVG:
    ''' SVG generators '''
    def __init__(self):
        self._scale = 1
        self._stroke_width = 1
        self._fill = '#FFFFFF'
        self._stroke = '#000000'

    def _svg_style(self, extras=""):
        return "%s%s%s%s%s%f%s%s%s" % (" style=\"fill:", self._fill, ";stroke:",
                                       self._stroke, ";stroke-width:",
                                       self._stroke_width, ";", extras,
                                       "\" />\n")

    def _svg_xo(self):
        self.set_stroke_width(3.5)
        svg_string = "<path d=\"M33.233,35.1l10.102,10.1c0.752,0.75,1.217,1.783,1.217,2.932   c0,2.287-1.855,4.143-4.146,4.143c-1.145,0-2.178-0.463-2.932-1.211L27.372,40.961l-10.1,10.1c-0.75,0.75-1.787,1.211-2.934,1.211   c-2.284,0-4.143-1.854-4.143-4.141c0-1.146,0.465-2.184,1.212-2.934l10.104-10.102L11.409,24.995   c-0.747-0.748-1.212-1.785-1.212-2.93c0-2.289,1.854-4.146,4.146-4.146c1.143,0,2.18,0.465,2.93,1.214l10.099,10.102l10.102-10.103   c0.754-0.749,1.787-1.214,2.934-1.214c2.289,0,4.146,1.856,4.146,4.145c0,1.146-0.467,2.18-1.217,2.932L33.233,35.1z\""
        svg_string += self._svg_style()
        svg_string += "\n<circle cx=\"27.371\" cy=\"10.849\" r=\"8.122\""
        svg_string += self._svg_style()
        return svg_string

    def _background(self, scale):
        return self._svg_rect(54.5 * scale, 54.5 * scale, 4, 4, 0.25, 0.25)

    def header(self, scale=1, background=True):
        svg_string = "<?xml version=\"1.0\" encoding=\"UTF-8\""
        svg_string += " standalone=\"no\"?>\n"
        svg_string += "<!-- Created with Emacs -->\n"
        svg_string += "<svg\n"
        svg_string += "   xmlns:svg=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   xmlns=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   version=\"1.0\"\n"
        svg_string += "%s%f%s" % ("   width=\"", scale * 55 * self._scale,
                                  "\"\n")
        svg_string += "%s%f%s" % ("   height=\"", scale * 55 * self._scale,
                                  "\">\n")
        svg_string += "%s%f%s%f%s" % ("<g\n       transform=\"matrix(",
                                      self._scale, ",0,0,", self._scale,
                                      ",0,0)\">\n")
        if background:
            svg_string += self._background(scale)
        return svg_string

    def footer(self):
        svg_string = "</g>\n"
        svg_string += "</svg>\n"
        return svg_string

    #
    # Utility functions
    #
    def set_scale(self, scale=1.0):
        self._scale = scale

    def set_colors(self, colors):
        self._stroke = colors[0]
        self._fill = colors[1]

    def set_stroke_width(self, stroke_width=1.0):
        self._stroke_width = stroke_width

def generate_xo(scale=1, colors=["#FFFFFF", "#000000"]):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors(colors)
    svg_string = svg.header(background=False)
    svg_string += svg._svg_xo()
    svg_string += svg.footer()
    return svg_string
