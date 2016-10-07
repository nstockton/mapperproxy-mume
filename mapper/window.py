import pyglet
from pyglet.window import key
import Tolk

keys={
(key.F11,0):'toggle_fullscreen'
}

class Window(pyglet.window.Window):
	def __init__(self):
		caption='MPM'
		super(Window, self).__init__(caption=caption, resizable=True)
		Tolk.load()
		self.say=Tolk.output

	def on_key_press(self, sym, mod):
		k=(sym, mod)
		if k in keys:
			funcname='do_'+keys[k]
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

w=Window()
pyglet.app.run()