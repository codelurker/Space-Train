"""
Main file for the Space Train game engine. Run this.

-Add scene folder to PYTHONPATH so we can import scene scripts
-Open window and initialize game
-Start pyglet run loop
"""

import math, os, sys, json

import pyglet

pyglet.options['debug_gl'] = False

import engine
from engine import gamestate, util
from engine import gamehandler, eventmanager

class AdventureWindow(pyglet.window.Window):
    """
    Basic customizations to Window, plus configuration.
    """
    def __init__(self, reset_save=False, reset_at_scene=None):
        reset_save = reset_save or reset_at_scene
        if util.settings.fullscreen:
            super(AdventureWindow,self).__init__(fullscreen=True, vsync=True)
        else:
            super(AdventureWindow,self).__init__(width=gamestate.norm_w, 
                                                 height=gamestate.norm_h, vsync=True)
        
        gamestate.main_window = self    # Make main window accessible to others.
                                        #   Necessary for convenient event juggling.
        gamestate.init_scale()          # Set up scaling transformations to have
                                        #   a consistent window size
        gamestate.event_manager = eventmanager.EventManager()
        
        pyglet.gl.glEnable(pyglet.gl.GL_BLEND)
        pyglet.gl.glBlendFunc(pyglet.gl.GL_SRC_ALPHA, pyglet.gl.GL_ONE_MINUS_SRC_ALPHA)
        pyglet.gl.glEnable(pyglet.gl.GL_LINE_SMOOTH)
        
        self.game_handler = None
        
        engine.init()                   # Set up resource paths
        
        self.init_load()

        with pyglet.resource.file(util.respath('game', 'info.json'), 'r') as game_info_file:
            self.game_info = json.load(game_info_file)
            self.game_info['reset_save'] = reset_save
            if reset_at_scene:
                self.game_info['first_scene'] = reset_at_scene
            self.set_caption(self.game_info["name"])
        
        # Stupid hack to get around pyglet loading bullshit
        pyglet.clock.schedule_once(self.finish_loading, 0.0000001)
    
    def init_load(self):
        self.load_fraction = 0.0
        self.load_batch = pyglet.graphics.Batch()
        img = pyglet.resource.image('actors/a_train_in_spain/badge.png')
        img.anchor_x = img.width/2
        img.anchor_y = img.height/2
        self.load_sprite = pyglet.sprite.Sprite(
            img, x=self.width/2, y=self.height*0.7, batch=self.load_batch
        )
        
        img = pyglet.resource.image('actors/a_train_in_spain/train.png')
        img.anchor_x = img.width
        img.anchor_y = 0
        self.crawler_sprite = pyglet.sprite.Sprite(img, x=0, y=self.height*0.12,
                                                   batch=self.load_batch)
        
        img = pyglet.resource.image('ui/track.png')
        img.anchor_x = img.width/2
        img.anchor_y = img.height
        self.track_sprite = pyglet.sprite.Sprite(img, x=self.width/2, y=self.height*0.12,
                                                 batch=self.load_batch)
        
        self.this_img = pyglet.text.Label('Loading...', anchor_x='center', anchor_y='bottom',
                                          font_size=36,
                                          x=self.width/2, y=self.height*0.14, batch=self.load_batch,
                                          color=(255,255,255,128))
        
        self.background_image = pyglet.resource.image(
                                'environments/the_vast_emptiness_of_space/0_0.png')
    
    def finish_loading(self, dt=0):
        self.preload()
        self.game_handler = gamehandler.GameHandler(**self.game_info)
        
        # Schedule drawing and update functions.
        # Draw really only needs 60 FPS, update can be faster.
        pyglet.clock.schedule_interval(self.on_draw, 1/60.0)
        pyglet.clock.schedule_interval(self.game_handler.update, 1/120.0)
    
    def preload(self):
        self.on_draw()
        self.flip()
        i = 0
        for s in ['options_appear.wav', 'select_1.wav', 'select_2.wav', 'select_3.wav', 
                  'select_4.wav', 'select_5.wav', 'select_6.wav', 'give.wav', 'take.wav']:
            pyglet.resource.media('sound/%s' % s, streaming=False)
        for item in util.preload:
            try:
                util.load_image(item)
            except pyglet.resource.ResourceNotFoundException:
                print "bad", item
            i += 1
            self.load_fraction = float(i)/float(len(util.preload))
            self.on_draw()
            self.flip()

    def on_draw(self, dt=0):
        if self.game_handler:
            self.game_handler.draw()
        else:
            util.draw.set_color(0,0,0)
            util.draw.rect(0,0,self.width,self.height)
            self.crawler_sprite.x = self.width*self.load_fraction
            util.draw.set_color(255,255,255,255)
            self.background_image.blit(0,0)
            self.load_batch.draw()
    
    def on_key_press(self, symbol, modifiers):
        # Override default behavior of escape key quitting
        if symbol == pyglet.window.key.ESCAPE:
            return pyglet.event.EVENT_HANDLED
    
    def on_close(self):
        self.game_handler.prompt_save_and_quit()
    

def run_game():
    sys.path.append(os.path.join(os.path.dirname(sys.argv[0]), 'game'))
    if len(sys.argv) == 2:
        if sys.argv[1] == 'newgame':
            main_window = AdventureWindow(True)
        else:
            main_window = AdventureWindow(True, sys.argv[1])
    else:
        main_window = AdventureWindow(True) # LOL
    pyglet.app.run()

if __name__ == '__main__':
    run_game()
