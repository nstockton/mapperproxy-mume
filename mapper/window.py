# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
###Some code borrowed from pymunk's debug drawing functions###

import pyglet
pyglet.options['debug_gl'] = False
from pyglet.window import key
from speechlight import Speech
import math
from collections import namedtuple
try:
	from Queue import Empty as QueueEmpty
except ImportError:
	from queue import Empty as QueueEmpty

from .constants import DIRECTIONS, TERRAIN_COLORS
from .utils import iterItems
from .vec2d import Vec2d

# Monkey patch range with xrange in Python2.
_range = range
try:
	range = xrange
except NameError:
	pass

DIRECTIONS_2D = frozenset(DIRECTIONS[:-2])
FPS = 60
KEYS={
(key.ESCAPE, 0): 'reset_zoom',
(key.LEFT, 0): 'adjust_size',
(key.RIGHT, 0): 'adjust_size',
(key.UP,0): 'adjust_spacer',
(key.DOWN, 0): 'adjust_spacer',
(key.F11, 0):'toggle_fullscreen'
}


DIRECTIONS_VEC2D = {
	'north': Vec2d(0, 1),
	'east': Vec2d(1, 0),
	'south': Vec2d(0, -1),
	'west': Vec2d(-1, 0)
	}

class Color(namedtuple("Color", ["r","g","b","a"])):
	"""Color tuple used by the debug drawing API.
	"""
	__slots__ = ()	

	def as_int(self):
		return int(self[0]), int(self[1]), int(self[2]), int(self[3])

	def as_float(self):
		return self[0]/255., self[1]/255., self[2]/255., self[3]/255.


class Window(pyglet.window.Window):
	def __init__(self, world):
		caption='MPM'
		super(Window, self).__init__(caption=caption, resizable=True, fullscreen=True, vsync=False)
		self.speech=Speech()
		self.say=self.speech.say
		self.maximize()
		self.world=world
		self._gui_queue = world._gui_queue
		self._gui_queue_lock = world._gui_queue_lock
		self.batch=pyglet.graphics.Batch()
		self.visible_rooms = {}
		self.visible_exits = {}
		pyglet.clock.schedule_interval_soft(self.queue_observer, 1.0 / FPS)
		self.current_room=None
		self._size=100.0
		self._spacer=10
		self.current_room_border1=0.05
		self.current_room_border2=0.3
		self.current_room_border=self.current_room_border2
		self.current_room_border_color=Color(255, 255, 255, 255)
		self.current_room_border_vl = None
		self.blink = True
		self.blink_rate = 2 #times per second
		if self.blink:
			pyglet.clock.schedule_interval_soft(self.border_blinker, 1.0/self.blink_rate)
		self.exit_radius=10
		self.exit_color1=Color(255, 228, 225, 225)
		self.exit_color2=Color(0, 0, 0, 255)
		self.groups = tuple(pyglet.graphics.OrderedGroup(i) for i in range(5))

	@property
	def size(self):
		return self._size
	@size.setter
	def size(self, value):
		size=int(value)
		if value < 50:
			value=50
		elif value > 250:
			value=250
		self._size=value

	@property
	def spacer(self):
		return self._spacer
	@spacer.setter
	def spacer(self,value):
		value = int(value)
		if value < 0:
			value = 0
		elif value > 20:
			value = 20
		self._spacer=value

	@property
	def spacer_as_float(self):
		return self.spacer/10.0

	@property
	def cx(self):
		return self.width/2.0

	@property
	def cy(self):
		return self.height/2.0

	@property
	def cp(self):
		return Vec2d(self.cx,self.cy)

	def queue_observer(self, dt):
		with self._gui_queue_lock:
			while not self._gui_queue.empty():
				try:
					e = self._gui_queue.get_nowait()
					if e is None:
						self.close()
						break
					self.dispatch_event(e[0], *e[1:])
				except QueueEmpty:
					break

	def border_blinker(self, dt):
		b, b1, b2 = self.current_room_border, self.current_room_border1, self.current_room_border2
		if b == b1:
			self.current_room_border=b2
		else:
			self.current_room_border=b1
		self._draw_current_room_border()

	def on_draw(self):
		pyglet.gl.glClearColor(0,0,0,0)
		self.clear()
		self.batch.draw()

	def on_map_sync(self, currentRoom):
		self.current_room=currentRoom
		self.redraw()

	def on_resize(self, width, height):
		super(Window, self).on_resize(width, height)
		if self.current_room is not None:
			self.redraw()

	def on_key_press(self, sym, mod):
		k=(sym, mod)
		if k in KEYS:
			funcname='do_'+KEYS[k]
			try:
				func=getattr(self, funcname)
				try:
					func(sym, mod)
				except Exception as e:
					self.say(e.message)
			except AttributeError:
				self.say('Invalid key assignment for key {}. No such function {}.'.format(k, funcname))

	def do_toggle_fullscreen(self, sym, mod):
		self.set_fullscreen(not self.fullscreen)

	def do_adjust_spacer(self, sym, mod):
		if sym== key.DOWN:
			self.spacer-=1
		elif sym == key.UP:
			self.spacer += 1
		self.say(str(self.spacer_as_float))
		self.redraw()

	def do_adjust_size(self, sym, mod):
		if sym == key.LEFT:
			self.size -= 10.0
		elif sym == key.RIGHT:
			self.size += 10.0
		self.say(str(self.size))
		self.redraw()

	def do_reset_zoom(self, sym, mod):
		self.size=100
		self.spacer=10
		self.redraw()

	def draw_circle(self, cp, radius, color, line_color=None, angle=0.0):
		cp = Vec2d(cp)
		#http://slabode.exofire.net/circle_draw.shtml
		num_segments = int(4 * math.sqrt(radius))
		theta = 2 * math.pi / num_segments
		c = math.cos(theta)
		s = math.sin(theta)
		x = radius # we start at angle 0
		y = 0
		ps = []
		for i in range(num_segments):
			ps += [Vec2d(cp.x + x, cp.y + y)]
			t = x
			x = c * x - s * y
			y = s * t + c * y
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		ps2 = [ps[0]]
		for i in range(1, int(len(ps)+1/2)):
			ps2.append(ps[i])
			ps2.append(ps[-i])
		ps = ps2
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
				vs += [p.x, p.y]
		c = cp + Vec2d(radius, 0).rotated(angle)
		cvs = [cp.x, cp.y, c.x, c.y]
		bg = self.groups[0]
		fg = self.groups[1]
		l = len(vs)//2
		if line_color is None:
			line_color=color
		return (self.batch.add(len(vs)//2, mode, bg,
				('v2f', vs),
				('c4B', color.as_int()*l)), \
		self.batch.add(2, pyglet.gl.GL_LINES, fg,
				('v2f', cvs),
				('c4B', line_color.as_int()*2)))

	def draw_segment(self, a, b, color, group=None):
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		line = (int(pv1.x), int(pv1.y), int(pv2.x), int(pv2.y))
		return self.batch.add(2, pyglet.gl.GL_LINES, group,
					('v2i', line),
					('c4B', color.as_int() * 2))

	def fat_segment_vertices(self, a, b, radius): 
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		d = pv2 - pv1
		a = -math.atan2(d.x, d.y)
		radius = max(radius, 1)
		dx = radius * math.cos(a)
		dy = radius * math.sin(a)
		p1 = pv1 + Vec2d(dx,dy)
		p2 = pv1 - Vec2d(dx,dy)
		p3 = pv2 + Vec2d(dx,dy)
		p4 = pv2 - Vec2d(dx,dy)
		vs = [i for xy in [p1,p2,p3]+[p2,p3,p4] for i in xy]
		return vs

	def draw_fat_segment(self, a, b, radius, color, group=None):
		vs=self.fat_segment_vertices(a, b, radius)
		l = len(vs)//2
		return self.batch.add(l,pyglet.gl.GL_TRIANGLES, group,
					('v2f', vs),
					('c4B', color.as_int() * l))

	def corners_2_vertices(self,ps):
		ps = [ps[1],ps[2], ps[0]] + ps[3:]
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
			vs += [p.x, p.y]
		return vs

	def draw_polygon(self, verts, color, group=None):
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		vs=self.corners_2_vertices(verts)
		l = len(vs)//2
		vl=self.batch.add(l, mode, group,
					('v2f', vs),
					('c4B', color.as_int()*l))
		return vl

	@property
	def cx(self):
		return self.width/2.0
	@property
	def cy(self):
		return self.height/2.0
	@property
	def cp(self):
		return Vec2d(self.cx,self.cy)

	def num_rooms_to_draw(self):
		rooms_w=(self.width//self.size)//2
		rooms_h=(self.height//self.size)//2
		return (rooms_w,rooms_h,1)

	def _draw_current_room_border(self):
		cp=self.cp
		d1 = (self.size/2.0) * (1.0+self.current_room_border1)
		vs1=[cp-d1, cp-(d1,d1*-1), cp+d1, cp+(d1,d1*-1)]
		d2 = d1*(1.0+self.current_room_border)
		vs2=[cp-d2, cp-(d2,d2*-1), cp+d2, cp+(d2,d2*-1)]
		if self.current_room_border_vl is None:
			vl1 = self.draw_polygon(vs1, Color(0,0,0,255), group=self.groups[2])
			vl2 = self.draw_polygon(vs2, self.current_room_border_color, group=self.groups[1])
			self.current_room_border_vl = (vl1, vl2)
		else:
			vl1, vl2 = self.current_room_border_vl
			vl1.vertices = self.corners_2_vertices(vs1)
			vs=self.corners_2_vertices(vs2)
			vl2.vertices = vs
			vl2.colors=self.current_room_border_color.as_int()*(len(vs)//2)

	def equilateral_triangle(self, cp, radius, angle_degrees):
		v=Vec2d(radius, 0)
		v.rotate_degrees(angle_degrees)
		w=v.rotated_degrees(120)
		y=w.rotated_degrees(120)
		return [v+cp, w+cp, y+cp]

	def square_from_cp(self, cp, d):
		return [cp-d, cp-(d,d*-1), cp+d, cp+(d,d*-1)]

	def arrow_points(self, a, d, r):
		l=d-a
		h = (r*1.5)*math.sqrt(3)
		l.length -= h
		b=a+l
		l.length += h/3.0
		c=a+l
		return (b, c, l.angle_degrees)

	def arrow_vertices(self, a, d, r):
		b, c, angle = self.arrow_points(a, d, r)
		vs1 = self.fat_segment_vertices(a, b, r)
		vs2 = self.corners_2_vertices(self.equilateral_triangle(c, r*3, angle))
		return (vs1, vs2)

	def draw_arrow(self, a, d, radius, color, group=None):
		b, c, angle = self.arrow_points(a, d, radius)
		vl1 = self.draw_fat_segment(a, b, radius, color, group=group)
		vl2 = self.draw_polygon(self.equilateral_triangle(c, radius*3, angle), color, group=group)
		return (vl1, vl2)

	def draw_room(self, room, cp, group=None):
		try:
			color=Color(*TERRAIN_COLORS[room.terrain])
		except KeyError as e:
			self.world.output("Unknown terrain type '{}' @{}!".format(e.args[0], room.vnum))
			color=Color(0,0,0,0)
		d=self.size/2.0
		vs=self.square_from_cp(cp, d)
		if group is None:
			group=self.groups[0]
		if room.vnum not in self.visible_rooms:
			vl = self.draw_polygon(vs, color, group=group)
			self.visible_rooms[room.vnum] = [vl, room, cp]
		else:
			vl=self.visible_rooms[room.vnum][0]
			vl.vertices=self.corners_2_vertices(vs)
			self.batch.migrate(vl, pyglet.gl.GL_TRIANGLE_STRIP, group, self.batch)
			self.visible_rooms[room.vnum][2]=cp

	def draw_rooms(self, currentRoom=None):
		if currentRoom is None:
			currentRoom=self.current_room
		if self.blink: self._draw_current_room_border()
		self.draw_room(currentRoom, self.cp, group=self.groups[3])
		newrooms = {currentRoom.vnum}
		for vnum, room, x, y, z in self.world.getNeighborsFromRoom(start=currentRoom, radius=self.num_rooms_to_draw()):
			if z == 0:
				newrooms.add(vnum)
				d=Vec2d(x, y)*(self.size*(self.spacer_as_float+1.0))
				self.draw_room(room, self.cp + d)
		if not self.visible_rooms:
			return
		for dead in set(self.visible_rooms) - newrooms:
			self.visible_rooms[dead][0].delete()
			del self.visible_rooms[dead]

	def draw_exits(self):
		_d = self.size/2
		newexits=set()
		for vnum, item in iterItems(self.visible_rooms):
			vl, room, cp= item
			exits = set(room.exits) #normal exits list
			if not self.spacer:
				exits ^= DIRECTIONS_2D #swap NESW exits with directions you can't go. Leave up/down in place if present.
				for e in room.exits:
					if not self.world.isExitLogical(room.exits[e]): exits.add(e) #add any existing NESW exits that are illogical back to the exits set for processing later.
			for e in exits:
				name=vnum+e[0]
				exit = room.exits.get(e, None)
				dv = DIRECTIONS_VEC2D.get(e, None)
				if not e is None and e in {'up', 'down'}:
					if e == 'up':
						new_cp = cp+(0, self.size/4.0)
						angle=90
					elif e == 'down':
						new_cp = cp-(0, self.size/4.0)
						angle=-90
					if self.world.isExitLogical(exit):
						vs1=self.equilateral_triangle(new_cp, (self.size/4.0)+14, angle)
						vs2=self.equilateral_triangle(new_cp, self.size/4.0, angle)
						if name in self.visible_exits:
							vl1, vl2=self.visible_exits[name]
							vl1.vertices=self.corners_2_vertices(vs1)
							vl2.vertices=self.corners_2_vertices(vs2)
						else:
							vl1=self.draw_polygon(vs1, self.exit_color2, group=self.groups[4])
							vl2=self.draw_polygon(vs2, self.exit_color1, group=self.groups[4])
							self.visible_exits[name]=(vl1, vl2)
					elif exit.to in {'undefined', 'death'}:
						if exit.to == 'undefined':
							if name in self.visible_exits:
								vl = self.visible_exits[name]
								vl.x, vl.y = new_cp
							else:
								vl = pyglet.text.Label('?', font_name='Times New Roman', font_size=(self.size/100.0)*72, x=new_cp.x, y=new_cp.y, anchor_x='center', anchor_y='center', color=self.exit_color2, batch=self.batch, group=self.groups[4])
								self.visible_exits[name] = vl
						else: #death
							if name in self.visible_exits:
								vl = self.visible_exits[name]
								vl.x, vl.y = new_cp
							else:
								vl = pyglet.text.Label('X', font_name='Times New Roman', font_size=(self.size/100.0)*72, x=new_cp.x, y=new_cp.y, anchor_x='center', anchor_y='center', color=Color(255,0,0,255), batch=self.batch, group=self.groups[4])
								self.visible_exits[name] = vl
					else: #one-way, random, etc
						l=new_cp-cp
						l.length /=2
						a=new_cp - l
						d = new_cp +l
						r=(self.size/self.exit_radius)/2.0
						if name in self.visible_exits:
							vl1, vl2 = self.visible_exits[name]
							vs1, vs2 = self.arrow_vertices(a, d, r)
							vl1.vertices = vs1
							vl2.vertices = vs2
						else:
							vl1, vl2 = self.draw_arrow(a, d, r, self.exit_color2, group=self.groups[4])
							self.visible_exits[name] = (vl1, vl2)
				else:
					if self.spacer == 0:
						name += '-'
						if exit is None:
							color = self.exit_color2
						elif exit.to == 'undefined':
							color = Color(0, 0, 255, 255)
						elif exit.to == 'death':
							color = Color (255, 0, 0, 255)
						else:
							color = Color (0, 255, 0, 255)
						a, b, c, d = self.square_from_cp(cp, _d)
						if e == 'west':
							s = (a, b)
						elif e == 'north':
							s = (b, c)
						elif e == 'east':
							s = (c, d)
						elif e == 'south':
							s = (d, a)
						if name in self.visible_exits:
							vl = self.visible_exits[name]
							vl.vertices = self.fat_segment_vertices(s[0], s[1], self.size/self.exit_radius/2.0)
							vl.colors = color*(len(vl.colors)/4)
						else:
							self.visible_exits[name] = self.draw_fat_segment(s[0], s[1], self.size/self.exit_radius, color, group=self.groups[4])
					else:
						if self.world.isExitLogical(exit):
							l = (self.size*self.spacer_as_float)/2
							a=cp+(dv*_d)
							b=a+(dv*l)
							if name in self.visible_exits:
								vl=self.visible_exits[name]
								vs=self.fat_segment_vertices(a, b, self.size/self.exit_radius)
								vl.vertices=vs
							else:
								self.visible_exits[name] = self.draw_fat_segment(a, b, self.size/self.exit_radius, self.exit_color1, group=self.groups[4])
						elif exit.to in {'undefined', 'death'}:
							l = (self.size*0.75)
							new_cp = cp + dv*l
							if exit.to == 'undefined':
								if name in self.visible_exits:
									vl = self.visible_exits[name]
									vl.x, vl.y = new_cp
								else:
									vl = pyglet.text.Label('?', font_name='Times New Roman', font_size=(self.size/100.0)*72, x=new_cp.x, y=new_cp.y, anchor_x='center', anchor_y='center', color=self.exit_color1, batch=self.batch, group=self.groups[4])
									self.visible_exits[name] = vl
							else: #death
								if name in self.visible_exits:
									vl = self.visible_exits[name]
									vl.x, vl.y = new_cp
								else:
									vl = pyglet.text.Label('X', font_name='Times New Roman', font_size=(self.size/100.0)*72, x=new_cp.x, y=new_cp.y, anchor_x='center', anchor_y='center', color=Color(255,0,0,255), batch=self.batch, group=self.groups[4])
									self.visible_exits[name] = vl
						else: #one-way, random, etc.
							color = self.exit_color1
							l = (self.size*self.spacer_as_float)/2
							a=cp+(dv*_d)
							d=a+(dv*l)
							r = ((self.size/self.exit_radius)/2.0)*self.spacer_as_float
							if name in self.visible_exits:
								vl1, vl2=self.visible_exits[name]
								vs1, vs2=self.arrow_vertices(a, d, r)
								vl1.vertices=vs1
								vl1.colors = color*(len(vl1.colors)//4)
								vl2.vertices=vs2
								vl2.colors = color*(len(vl2.colors)//4)
							else:
								self.visible_exits[name] = self.draw_arrow(a, d, r, color, group=self.groups[4])
				newexits.add(name)
		for dead in set(self.visible_exits) - newexits:
			try:
				try:
					self.visible_exits[dead].delete()
				except AttributeError:
					for d in self.visible_exits[dead]:
						d.delete()
			except AssertionError:
				pass
			del self.visible_exits[dead]

	def redraw(self):
		self.draw_rooms()
		self.draw_exits()


Window.register_event_type('on_map_sync')
