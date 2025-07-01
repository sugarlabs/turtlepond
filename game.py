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

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

import cairo
import os
import time

from math import sqrt, pi
from random import uniform

from sugar3.activity.activity import get_activity_root

from gettext import gettext as _

import traceback
import logging
_logger = logging.getLogger('turtle-in-a-pond-activity')

try:
    from sugar3.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from sprites import Sprites, Sprite

FILL = 1
STROKE = 0
DOT_SIZE = 20
DEFAULT_GRID_SIZE = 13
DOT_SIZE_GAMEOVER = 70
CIRCLE = [[(0, -1), (1, 0), (0, 1), (-1, 1), (-1, 0), (-1, -1)],
          [(1, -1), (1, 0), (1, 1), (0, 1), (-1, 0), (0, -1)]]
''' Simple strategy: head to daylight or randomly check for an open dot
    turtle is the (col, row) of the current turtle position '''
BEGINNER_STRATEGY = 'def _turtle_strategy(self, turtle):\n\
    dots = self._surrounding_dots(turtle)\n\
    n = int(uniform(0, 6))\n\
    for i in range(6):\n\
        if not self._dots[dots[(i + n) % 6]].type:\n\
            self._orientation = (i + n) % 6\n\
            return self._dot_to_grid(dots[(i + n) % 6])\n\
    self._orientation = (i + n) % 6\n\
    return turtle\n'
INTERMEDIATE_STRATEGY = 'def _turtle_strategy(self, turtle):\n\
    dots = self._surrounding_dots(turtle)\n\
    for i in range(6):  # search for an edge\n\
        if self._dots[dots[i]].type is None:\n\
            self._orientation = i\n\
            return self._dot_to_grid(dots[i])\n\
    if self._daylight_ahead(turtle):\n\
        return self._dot_to_grid(dots[self._orientation])\n\
    n = int(uniform(0, 6))  # choose a random orientation\n\
    for i in range(6):  # search for an opening\n\
        if not self._dots[dots[(i + n) % 6]].type:\n\
            self._orientation = (i + n) % 6\n\
            return self._dot_to_grid(dots[(i + n) % 6])\n\
    return turtle\n'
EXPERT_STRATEGY = 'def _turtle_strategy(self, turtle):\n\
    dots = self._surrounding_dots(turtle)\n\
    for i in range(6):\n\
        if self._dots[dots[i]].type is None:\n\
            self._orientation = i\n\
            return self._dot_to_grid(dots[i])\n\
    dots_ordered_by_weight = self._ordered_weights(turtle)\n\
    for i in range(6):\n\
        self._orientation = dots.index(dots_ordered_by_weight[i])\n\
        if self._daylight_ahead(turtle):\n\
            return self._dot_to_grid(dots[self._orientation])\n\
    n = int(uniform(0, 6))\n\
    for i in range(6):\n\
        if not self._dots[dots[(i + n) % 6]].type:\n\
            self._orientation = (i + n) % 6\n\
            return self._dot_to_grid(dots[(i + n) % 6])\n\
    self._orientation = (i + n) % 6\n\
    return turtle\n'


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self._activity = parent
        self._colors = colors

        self._canvas = canvas
        parent.show_all()

        self._canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._canvas.connect("draw", self.__draw_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)

        self._width = Gdk.Screen.width()
        self._height = Gdk.Screen.height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._height / (14.0 * DOT_SIZE * 1.2)
        self._scale_gameover = self._height / (4.0 * DOT_SIZE_GAMEOVER * 1.2)
        self._dot_size = int(DOT_SIZE * self._scale)
        self._dot_size_gameover = int(DOT_SIZE_GAMEOVER * self._scale)
        self._turtle_offset = 0
        self._space = int(self._dot_size / 5.)
        self._space_gameover = int(self._dot_size_gameover / 5.)
        self._orientation = 0
        self.level = 0
        self.classic_mode = True
        self.custom_strategy = None
        self.strategies = [BEGINNER_STRATEGY, INTERMEDIATE_STRATEGY,
                           EXPERT_STRATEGY, self.custom_strategy]
        self.strategy = self.strategies[self.level]
        self.sizes = [13, 12, 11, 10]
        self.size = self.sizes[self.level]
        self._timeout_id = None
        self.best_time = self.load_best_time()
        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self._dots = []
        self._gameover = []
        self._your_time = []
        self._best_time = []
        self._win_lose = []

        # Put a turtle at the center of the screen...
        self._turtle_images = []
        self._rotate_turtle(self._new_turtle())
        self._turtle = Sprite(self._sprites, 0, 0,
                              self._turtle_images[0])
        # ...and initialize.
        self._all_clear()

    def _init_grid(self):
        self._dots = []
        for y in range(self.size):
            for x in range(self.size):
                offset_x = int((self._width - self.size * (self._dot_size + \
                                      self._space) - self._space) / 2.)
                if y % 2 == 1:
                    offset_x += int((self._dot_size + self._space) / 2.)
                if x == 0 or y == 0 or x == self.size - 1 or y == self.size - 1:
                    self._dots.append(
                        Sprite(self._sprites,
                               offset_x + x * (self._dot_size + self._space),
                               y * (self._dot_size + self._space),
                               self._new_dot('#B0B0B0', self._dot_size)))
                else:
                    self._dots.append(
                        Sprite(self._sprites,
                               offset_x + x * (self._dot_size + self._space),
                               y * (self._dot_size + self._space),
                               self._new_dot(self._colors[FILL],
                                             self._dot_size)))
                    self._dots[-1].type = False  # not set
                self._dots[-1].set_layer(100)  # not set

    def _move_turtle(self, pos):
        ''' Move turtle and add its offset '''
        self._turtle.move(pos)
        self._turtle.move_relative(
            (-self._turtle_offset, -self._turtle_offset))

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''
        # Clear dots
        for gameover_shape in self._gameover:
            gameover_shape.hide()
        for win_lose_shape in self._win_lose:
            win_lose_shape.hide()
        for your_time_shape in self._your_time:
            your_time_shape.hide()
        for highscore_shape in self._best_time:
            highscore_shape.hide()
        for sprite in self._dots:
            sprite.hide()
        self._init_grid()
        self._turtle.set_layer(100)
        # Recenter the turtle
        self._move_turtle(self._dots[int(self.size * (self.size + 1 - self.size % 2) / 2)].get_xy())
        self._turtle.set_shape(self._turtle_images[0])
        self._set_label('')
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def new_game(self, saved_state=None):
        ''' Start a new game. '''
        self.gameover_flag = False
        self.game_lost = False
        self.strategy = self.strategies[self.level]
        self.size =  DEFAULT_GRID_SIZE if self.classic_mode else self.sizes[self.level]
        self._all_clear()
        # Fill in a few dots to start
        for i in range(15):
            n = int(uniform(0, self.size * self.size))
            if self._dots[n].type is not None:
                self._dots[n].type = True
                self._dots[n].set_shape(self._new_dot(self._colors[STROKE],
                                        self._dot_size))
        # Calculate the distances to the edge
        self._initialize_weights()
        self.game_start_time = time.time()
        self._timeout_id = None

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        self._activity.status.set_label(string)

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = list(map(int, event.get_coords()))

        spr = self._sprites.find_sprite((x, y), inverse=True)
        if spr == None:
            return

        if spr.type is not None and not spr.type:
            spr.type = True
            spr.set_shape(self._new_dot(self._colors[STROKE], self._dot_size))
            self._weights[self._dots.index(spr)] = 1000
            self._test_game_over(self._move_the_turtle())
        return True

    def _find_the_turtle(self):
        turtle_pos = self._turtle.get_xy()
        turtle_dot = None
        for dot in self._dots:
            pos = dot.get_xy()
            # Turtle is offset
            if pos[0] == turtle_pos[0] + self._turtle_offset and \
               pos[1] == turtle_pos[1] + self._turtle_offset:
                turtle_dot = self._dots.index(dot)
                break
        if turtle_dot is None:
            _logger.debug('Cannot find the turtle...')
            return None
        return turtle_dot

    def _move_the_turtle(self):
        ''' Move the turtle after each click '''
        self._turtle_dot = self._find_the_turtle()
        if self._turtle_dot is None:
            return

        # Given the col and row of the turtle, do something
        new_dot = self._grid_to_dot(
            self._my_strategy_import(self.strategy,
                                     self._dot_to_grid(self._turtle_dot)))
        self._move_turtle(self._dots[new_dot].get_xy())
        # And set the orientation
        self._turtle.set_shape(self._turtle_images[self._orientation])

        return new_dot

    def _test_game_over(self, new_dot):
        ''' Check to see if game is over '''
        if new_dot is None:
            return
        if self._dots[new_dot].type is None:
            # Game-over feedback
            self._once_around = False
            self.game_stop_time = time.time()
            self.gameover_flag = True
            self._happy_turtle_dance()
            self._timeout_id = GLib.timeout_add(10000, self._game_over)
            return True
        c = int(self._turtle_dot / self.size) % 2
        if self._dots[
            new_dot + CIRCLE[c][0][0] + self.size * CIRCLE[c][0][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][1][0] + self.size * CIRCLE[c][1][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][2][0] + self.size * CIRCLE[c][2][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][3][0] + self.size * CIRCLE[c][3][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][4][0] + self.size * CIRCLE[c][4][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][5][0] + self.size * CIRCLE[c][5][1]].type:
           # Game-over feedback
           for dot in self._dots:
               dot.set_label(':)')
               self.game_stop_time = time.time()
               self.gameover_flag = True
           self._timeout_id = GLib.timeout_add(4000, self._game_over)
           return True
        return False

    def _game_over(self):
        best_seconds = self.best_time % 60
        best_minutes = self.best_time // 60
        self.elapsed_time = int(self.game_stop_time - self.game_start_time)
        second = self.elapsed_time % 60
        minute = self.elapsed_time // 60
        for dot in self._dots:
            dot.hide()
        self._turtle.hide()

        offset_y = int(self._space_gameover / 4.)
        offset_x = int((self._width - 6 * self._dot_size_gameover -
                       5 * self._space_gameover) / 2.)
        y = 1.5
        for x in range(2, 6):
            self._gameover.append(
                Sprite(self._sprites,
                       offset_x + (x - 0.50) * self._dot_size_gameover,
                       y * (self._dot_size + self._space) + offset_y,
                       self._new_dot(self._colors[FILL],
                                     self._dot_size_gameover)))
            self._gameover[-1].type = -1  # No image
            self._gameover[-1].set_label_attributes(72)
        text = [
            "☻",
            " Game ",
            " Over ",
            "☻"
        ]
        self.rings(len(text), text, self._gameover)
        y = 4.5
        for x in range(2, 6):
            self._win_lose.append(
                Sprite(self._sprites,
                       offset_x + (x - 0.50) * self._dot_size_gameover,
                       y * (self._dot_size + self._space) + offset_y,
                       self._new_dot(self._colors[FILL],
                                     self._dot_size_gameover)))
            self._win_lose[-1].type = -1  # No image
            self._win_lose[-1].set_label_attributes(72)
        text_win_best_time = [
            "☻",
            "  YOU  ",
            "  WON  ",
            "☻"
        ]
        text_lose = [
            "☹",
            "   YOU   ",
            "  LOST  ",
            "☹"
        ]
        text_win = [
            "☻",
            " GOOD ",
            "   JOB  ",
            "☻"
        ]
        if self.game_lost:
            self.rings(len(text_lose), text_lose, self._win_lose)
        elif self.elapsed_time <= self.best_time:
            self.rings(
                len(text_win_best_time),
                text_win_best_time,
                self._win_lose)
        else:
            self.rings(len(text_win), text_win, self._win_lose)
        y = 7.5
        for x in range(2, 5):
            self._your_time.append(
                Sprite(self._sprites,
                       offset_x + x * self._dot_size_gameover,
                       y * (self._dot_size + self._space),
                       self._new_dot(self._colors[FILL],
                                     self._dot_size_gameover)))
            self._your_time[-1].type = -1  # No image
            self._your_time[-1].set_label_attributes(72)
        text = [
            "  your  ",
            " time:  ",
            (' {:02d}:{:02d} '.format(minute, second))
        ]
        self.rings(len(text), text, self._your_time)
        y = 10.5
        for x in range(2, 5):
            self._best_time.append(
                Sprite(self._sprites,
                       offset_x + x * self._dot_size_gameover,
                       y * (self._dot_size + self._space),
                       self._new_dot(self._colors[FILL],
                                     self._dot_size_gameover)))
            self._best_time[-1].type = -1  # No image
            self._best_time[-1].set_label_attributes(72)
        if self.elapsed_time <= self.best_time and not self.game_lost:
            self.best_time = self.elapsed_time
            best_seconds = second
            best_minutes = minute
        text = [
            "  best  ",
            " time:  ",
            (' {:02d}:{:02d} '.format(best_minutes, best_seconds))
        ]
        self.rings(len(text), text, self._best_time)
        self.save_best_time()
        self._timeout_id = GLib.timeout_add(7000, self.new_game)

    def rings(self, num, text, shape):
        i = 0
        for x in range(num):
            shape[x].type = -1
            shape[x].set_shape(self._new_dot(
                        self._colors[FILL], self._dot_size_gameover))
            shape[x].set_label(text[i])
            shape[x].set_layer(100)
            i += 1

    def _grid_to_dot(self, pos):
        ''' calculate the dot index from a column and row in the grid '''
        return pos[0] + pos[1] * self.size

    def _dot_to_grid(self, dot):
        ''' calculate the grid column and row for a dot '''
        return [dot % self.size, int(dot / self.size)]

    def _happy_turtle_dance(self):
        ''' Turtle dances along the edge '''
        self.game_lost = True
        i = self._find_the_turtle()
        if i == 0:
            if self._once_around:
                return
            else:
                self._once_around = True
        _logger.debug(i)
        x, y = self._dot_to_grid(i)
        if y == 0:
            x += 1
        if x == 0:
            y -= 1
        if x == self.size - 1:
            y += 1
        if y == self.size - 1:
            x -= 1
        i = self._grid_to_dot((x, y))
        self._dots[i].set_label(':)')
        self._move_turtle(self._dots[i].get_xy())
        self._orientation += 1
        self._orientation %= 6
        self._turtle.set_shape(self._turtle_images[self._orientation])
        self._timeout_id = GLib.timeout_add(250, self._happy_turtle_dance)

    def _ordered_weights(self, pos):
        ''' Returns the list of surrounding points sorted by their
        distance to the edge '''
        dots = self._surrounding_dots(pos)
        dots_and_weights = []
        for dot in dots:
            dots_and_weights.append((dot, self._weights[dot]))
        sorted_dots = sorted(dots_and_weights, key=lambda foo: foo[1])
        for i in range(6):
            dots[i] = sorted_dots[i][0]
        return dots

    def _daylight_ahead(self, pos):
        ''' Returns true if there is a straight path to the edge from
        the current position/orientation '''
        dots = self._surrounding_dots(pos)
        while True:
            dot_type = self._dots[dots[self._orientation]].type
            if dot_type is None:
                return True
            elif dot_type:
                return False
            else:  # keep looking
                pos = self._dot_to_grid(dots[self._orientation])
                dots = self._surrounding_dots(pos)

    def _surrounding_dots(self, pos):
        ''' Returns dots surrounding a position in the grid '''
        dots = []
        evenodd = pos[1] % 2
        for i in range(6):
            col = pos[0] + CIRCLE[evenodd][i][0]
            row = pos[1] + CIRCLE[evenodd][i][1]
            dots.append(self._grid_to_dot((col, row)))
        return dots

    def _initialize_weights(self):
        ''' How many steps to an edge? '''
        self._weights = []
        for d, dot in enumerate(self._dots):
            if dot.type is None:
                self._weights.append(0)
            elif dot.type:
                self._weights.append(1000)
            else:
                pos = self._dot_to_grid(d)
                pos2 = (self.size - pos[0], self.size - pos[1])
                self._weights.append(min(min(pos[0], pos2[0]),
                                         min(pos[1], pos2[1])))
    def _my_strategy_import(self, f, arg):
        ''' Run Python code passed as argument '''
        userdefined = {}
        try:
            exec(f, globals(), userdefined)
            return userdefined['_turtle_strategy'](self, arg)
        except ZeroDivisionError as e:
            self._set_label('Python zero-divide error: {}'.format(e))
        except ValueError as e:
            self._set_label('Python value error: {}'.format(e))
        except SyntaxError as e:
            self._set_label('Python syntax error: {}'.format(e))
        except NameError as e:
            self._set_label('Python name error: {}'.format(e))
        except OverflowError as e:
            self._set_label('Python overflow error: {}'.format(e))
        except TypeError as e:
            self._set_label('Python type error: {}'.format(e))
        except:
            self._set_label('Python error')
        traceback.print_exc()
        return None

    def __draw_cb(self, canvas, cr):
        self._sprites.redraw_sprites(cr=cr)

    def do_expose_event(self, event):
        ''' Handle the expose-event by drawing '''
        # Restrict Cairo to the exposed area
        cr = self._canvas.window.cairo_create()
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()
        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        Gtk.main_quit()

    def _new_dot(self, color, dot_size):
        ''' generate a dot of a color color '''
        self._stroke = color
        self._fill = color
        self._svg_width = dot_size
        self._svg_height = dot_size
        return svg_str_to_pixbuf(
            self._header() + \
            self._circle(dot_size / 2., dot_size / 2.,
                         dot_size / 2.) + \
            self._footer())

    def _new_turtle(self):
        ''' generate a turtle '''
        self._svg_width = self._dot_size * 2
        self._svg_height = self._dot_size * 2
        self._stroke = '#101010'
        self._fill = '#404040'
        return svg_str_to_pixbuf(
            self._header() + \
            self._turtle() + \
            self._footer())

    def _rotate_turtle(self, image):
        w, h = image.get_width(), image.get_height()
        nw = nh = int(sqrt(w * w + h * h))
        for i in range(6):
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, nw, nh)
            context = cairo.Context(surface)
            context.translate(w / 2., h / 2.)
            context.rotate((30 + i * 60) * pi / 180.)
            context.translate(-w / 2., -h / 2.)
            Gdk.cairo_set_source_pixbuf(context, image, 0, 0)
            context.rectangle(0, 0, nw, nh)
            context.fill()
            self._turtle_images.append(surface)
        self._turtle_offset = int(self._dot_size / 2.)

    def _header(self):
        return '<svg\n' + 'xmlns:svg="http://www.w3.org/2000/svg"\n' + \
            'xmlns="http://www.w3.org/2000/svg"\n' + \
            'xmlns:xlink="http://www.w3.org/1999/xlink"\n' + \
            'version="1.1"\n' +  'width="' + str(self._svg_width) +  '"\n' + \
            'height="' + str(self._svg_height) + '">\n'

    def _circle(self, r, cx, cy):
        return '<circle style="fill:' + str(self._fill) + ';stroke:' + \
            str(self._stroke) +  ';" r="' + str(r - 0.5) +  '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _footer(self):
        return '</svg>\n'

    def _turtle(self):
        svg = '<g\ntransform="scale(%.1f, %.1f)">\n' % (
            self._svg_width / 60., self._svg_height / 60.)
        svg += '%s%s%s%s%s%s%s%s' % ('  <path d="M 27.5 48.3 ',
              'C 26.9 48.3 26.4 48.2 25.9 48.2 L 27.2 50.5 L 28.6 48.2 ',
              'C 28.2 48.2 27.9 48.3 27.5 48.3 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke,
              '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 40.2 11.7 ',
              'C 38.0 11.7 36.2 13.3 35.8 15.3 ',
              'C 37.7 16.7 39.3 18.4 40.5 20.5 ',
              'C 42.8 20.4 44.6 18.5 44.6 16.2 ',
              'C 44.6 13.7 42.6 11.7 40.2 11.7 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 40.7 39.9 ',
              'C 39.5 42.1 37.9 44.0 35.9 45.4 ',
              'C 36.4 47.3 38.1 48.7 40.2 48.7 ',
              'C 42.6 48.7 44.6 46.7 44.6 44.3 ',
              'C 44.6 42.0 42.9 40.2 40.7 39.9 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 14.3 39.9 ',
              'C 12.0 40.1 10.2 42.0 10.2 44.3 ',
              'C 10.2 46.7 12.2 48.7 14.7 48.7 ',
              'C 16.7 48.7 18.5 47.3 18.9 45.4 ',
              'C 17.1 43.9 15.5 42.1 14.3 39.9 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 19.0 15.4 ',
              'C 18.7 13.3 16.9 11.7 14.7 11.7 ',
              'C 12.2 11.7 10.2 13.7 10.2 16.2 ',
              'C 10.2 18.5 12.1 20.5 14.5 20.6 ',
              'C 15.7 18.5 17.2 16.8 19.0 15.4 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 27.5 12.6 ',
              'C 29.4 12.6 31.2 13.0 32.9 13.7 ',
              'C 33.7 12.6 34.1 11.3 34.1 9.9 ',
              'C 34.1 6.2 31.1 3.2 27.4 3.2 ',
              'C 23.7 3.2 20.7 6.2 20.7 9.9 ',
              'C 20.7 11.3 21.2 12.7 22.0 13.7 ',
              'C 23.7 13.0 25.5 12.6 27.5 12.6 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s%s%s%s%s%s%s%s' % ('   <path d="M 43.1 30.4 ',
              'C 43.1 35.2 41.5 39.7 38.5 43.0 ',
              'C 35.6 46.4 31.6 48.3 27.5 48.3 ',
              'C 23.4 48.3 19.4 46.4 16.5 43.0 ',
              'C 13.5 39.7 11.9 35.2 11.9 30.4 ',
              'C 11.9 20.6 18.9 12.6 27.5 12.6 ',
              'C 36.1 12.6 43.1 20.6 43.1 30.4 Z" stroke_width="3.5" ',
              'fill="', self._fill, ';" stroke="', self._stroke, '" />\n')
        svg += '%s%s%s%s%s' % ('   <path d="M 25.9 33.8 L 24.3 29.1 ',
              'L 27.5 26.5 L 31.1 29.2 L 29.6 33.8 Z" stroke_width="3.5" ',
              'fill="', self._stroke, ';" stroke="none" />\n')
        svg += '%s%s%s%s%s%s' % ('   <path d="M 27.5 41.6 ',
              'C 23.5 41.4 22.0 39.5 22.0 39.5 L 25.5 35.4 L 30.0 35.5 ',
              'L 33.1 39.7 C 33.1 39.7 30.2 41.7 27.5 41.6 Z" ',
              'stroke_width="3.5" fill="', self._stroke,
              ';" stroke="none" />\n')
        svg += '%s%s%s%s%s%s' % ('   <path d="M 18.5 33.8 ',
              'C 17.6 30.9 18.6 27.0 18.6 27.0 L 22.6 29.1 L 24.1 33.8 ',
              'L 20.5 38.0 C 20.5 38.0 19.1 36.0 18.4 33.8 Z" ',
              'stroke_width="3.5" fill="', self._stroke,
              ';" stroke="none" />\n')
        svg += '%s%s%s%s%s%s' % ('   <path d="M 19.5 25.1 ',
              'C 19.5 25.1 20.0 23.2 22.5 21.3 ',
              'C 24.7 19.7 27.0 19.6 27.0 19.6 L 26.9 24.6 L 23.4 27.3 ',
              'L 19.5 25.1 Z" stroke_width="3.5" fill="', self._stroke,
              ';" stroke="none" />\n')
        svg += '%s%s%s%s%s%s' % ('   <path d="M 32.1 27.8 L 28.6 25.0 ',
              'L 29 19.8 C 29 19.8 30.8 19.7 33.0 21.4 ',
              'C 35.2 23.2 36.3 26.4 36.3 26.4 L 32.1 27.8 Z" ',
              'stroke_width="3.5" fill="', self._stroke,
              ';" stroke="none" />\n')
        svg += '%s%s%s%s%s%s' % ('   <path d="M 31.3 34.0 L 32.6 29.6 ',
              'L 36.8 28.0 C 36.8 28.0 37.5 30.7 36.8 33.7 ',
              'C 36.2 36.0 34.7 38.1 34.7 38.1 L 31.3 34.0 Z" ',
              'stroke_width="3.5" fill="', self._stroke,
              ';" stroke="none" />\n')
        svg += '</g>\n'
        return svg

    def save_best_time(self):
        file_path = os.path.join(get_activity_root(), 'data', 'best-time')
        best_time = [180]
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                best_time = fp.readlines()
        int_best_time = int(best_time[0])
        if not int_best_time <= self.elapsed_time and not self.game_lost:
            int_best_time = self.elapsed_time
        with open(file_path, "w") as fp:
            fp.write(str(int_best_time))

    def load_best_time(self):
        file_path = os.path.join(get_activity_root(), 'data', 'best-time')
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                highscore = fp.readlines()
            try:
                return int(highscore[0])
            except (ValueError, IndexError) as e:
                logging.exception(e)
                return 0
        return 0

def svg_str_to_pixbuf(svg_string):
    """ Load pixbuf from SVG string """
    pl = GdkPixbuf.PixbufLoader.new_with_type('svg') 
    pl.write(svg_string.encode())
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf
