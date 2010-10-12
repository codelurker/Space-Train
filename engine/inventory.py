"""
File:           inventory.py
Author:         Fred Hatfull
Description:    This class is responsible for managing and providing a graphical representation of a player's inventory. It should be managed by the UI class.
Notes: 

Inventory Life Cycle:
* Inventory should be instantiated with UI and should also follow the conventions of the singleton pattern (i.e. only one inventory object should ever exist).
* Inventory should be capable of tracking a player's objects throughout his/her game. 
* Inventory should manifest itself graphically as either an icon (closed) or an icon with a lengthy background upon which a player's items are displayed (open)
* Inventory should provide facilities for adding items to the inventory or sending items in the inventory to the game world (drag & drop)
* Inventory should be destroyed with UI at shutdown
"""


import copy

import json, pyglet

import gamestate, util

class Inventory(object):

    # Initialization
    def __init__(self):
        self.sprites = {}
        self.images = []
        self.batches = {}
        self.batches['open'] = pyglet.graphics.Batch()
        self.batches['closed'] = pyglet.graphics.Batch()
        self.sprites['open'] = []
        self.sprites['closed'] = []
        self.visible = True
        
        self.width = 5
                
        self.isopen = False
        
        # Create the inventory closed state first
        self.sprites['closed'].append( util.load_sprite(['ui', 'purse.png'], x = gamestate.norm_w, y = gamestate.norm_h, batch = self.batches['closed']) )
        self.translate_bottomleft_to_topright(self.sprites['closed'])
                      
        # Create the inventory open state now
        self.sprites['open'].append( util.load_sprite(['ui', 'purseopen.png'], x = gamestate.norm_w, y = gamestate.norm_h, batch = self.batches['open']) )
        self.translate_bottomleft_to_topright(self.sprites['open'])

        gamestate.event_manager.set_inventory(self)
    
    #needs to go in util sometime
    def translate_bottomleft_to_topright(self, sprites):
        # translate everything to where it needs to be
        x_trans = 0
        y_trans = 0
        for sprite in sprites:
            x_trans += sprite.width
            y_trans = sprite.height
        for sprite in sprites:
            sprite.x -= x_trans
            sprite.y -= y_trans
    
    def on_mouse_release(self, x, y, button, modifiers):
        if self.intersects_active_area(x, y):
            self.toggle()
            return pyglet.event.EVENT_HANDLED
        else:
            return pyglet.event.EVENT_UNHANDLED
            
    
    def toggle(self):
        self.isopen = not self.isopen
        
    def intersects_active_area(self, x, y):
        sprite_list = (self.sprites['open'] if self.isopen else self.sprites['closed'])
        for sprite in sprite_list:
            if(x > sprite.x and x < sprite.x + sprite.width and
               y > sprite.y and y < sprite.y + sprite.height):
                return True
        return False 
        
    # Render the inventory in the UI
    def draw(self, dt=0):
        #print self.isopen
        if self.visible:
            if(self.isopen is False):
                self.batches['closed'].draw()
            else:
                self.batches['open'].draw()