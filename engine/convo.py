"""
Starts, runs, and stops cutscenes.

The file format is JSON/YAML. Either syntax can be used, but YAML is easier on the eyes.

A conversation file should reside in its scene's data folder and have the extension ".convo".
At the top level, it is a dictionary with a few required keys and as many non-required keys
as you desire.

Required keys:

    # Animations
    at_rest:    # actor ID: image to show when actor is not speaking
        main: stand_right
        bean_salesman: stand_front
    
    speaking:   # actor ID: image to show when actor is speaking
        main: talk_right
        bean_salesman: stand_front
    
    variables:  # Variable name: initial value (can be updated with update_locals)
        bean_hate: false
        bean_interest: false
    
    # Dialogue entry point
    start:
        [action list]

Action list format:
    - command: argument
    - command: argument
    - ...

Commands:
    goto: <label>
        Start executing the action list under the top-level label <label>
        
        EXAMPLE: goto start
    
    give: <actor_name>
        Add a new instance of <actor_name> to the inventory with an ID of the form actor_name_#,
        where # is the highest unused number in this form.
    
    give: <actor_name> (new_id)
        Like give, but you can also specify the object's identifier string.
    
    actor_id: <text>
        Make an actor speak a phrase. Delay the next action.
        
        EXAMPLE:
            bean_salesman: What a nice day it is today!
    
    actor_id: <dictionary>
        Perform actions on one actor. Currently only accepts one key:
            action: <action_name>
                Calls actor.action_name()
        
        EXAMPLE:
            bean_salesman:
                action: jump
    
    update_animations:
        Update the animations dictionary (top level dictionary), like so:
        
        - update_animations:
            at_rest:
                main: stand_front
    
    update_locals:
        name: value
        name: value
        ...
        
        Set/update the values of any conversation-local variables
    
    update_globals:
        name: value
        name: value
        ...
        
        Set/update the values of any game global variables
    
    choice:
        <choice text>:
            [action list]
        <another choice>:
            [action list]
        
        Present a contextual action menu to the user with dialogue options.
        
        The action list accepts two extra commands:
            hide_after_use: true
                Do not show this choice again in this conversation.
            require: <local>
                Require that the conversation variable <local> be set to some true value
        
        (hide_after_use is somewhat redundant to update_locals+require, but it's convenient.)
"""

import collections
import functools
import itertools
import pyglet
import random
import re
import yaml

import actor, gamestate
from interpolator import LinearInterpolator

from util import draw

# Convenience function for creating defaultdicts that return None if key not present
nonedict = functools.partial(collections.defaultdict, lambda: None)

# Match 'give:' syntax
parens_match = re.compile(r'(?P<name>[^(]+\S+)\s+\((?P<id>[^)]+)\)')

colors = {
    'main': (255,201,215,255)
}

more_colors = itertools.cycle(random.sample([
    (229,201,255,255),
    (201,206,255,255),
    (201,249,255,255),
    (201,255,211,255),
    (255,255,201,255),
    (255,228,201,255),
    (255,201,201,255),
], 7))

multiline_w = 400

class Conversation(object):
    def __init__(self, scn, background=False):
        super(Conversation, self).__init__()
        self.scene = scn
        
        self.convo_name = None
        self.convo_info = None
        self.animations = None
        self.convo_lines = None
        self.convo_position = 0
        self.background = background
        self.convo_label = None
        self.text_color = (255,255,255,255)
        self.vertices_outline = None
        self.vertices_fill = None
    
    def delete(self):
        pass
    
    active = property(lambda self: self.convo_name is not None)
    
    def on_mouse_release(self, x, y, button, modifiers):
        """Skip speaking delay on mouse click"""
        if self.active and not self.scene.ui.cam:
            self.scene.clock.unschedule(self.next_line)
            self.next_line()
            return pyglet.event.EVENT_HANDLED
    
    def on_key_release(self, symbol, modifiers):
        if symbol == pyglet.window.key.SPACE:
            if self.active and not self.scene.ui.cam:
                self.scene.clock.unschedule(self.next_line)
                self.next_line()
                return pyglet.event.EVENT_HANDLED
    
    def draw(self):
        """Draw dialogue box and text"""
        if self.convo_label:
            draw.set_color(0,0,0,1)
            pyglet.graphics.draw(9, pyglet.gl.GL_TRIANGLES,('v2f', self.vertices_fill))
            draw.set_color(*map(lambda c:c/255.0, self.text_color))
            pyglet.graphics.draw(len(self.vertices_outline)/2,
                                 pyglet.gl.GL_LINE_LOOP, ('v2f', self.vertices_outline))
            self.convo_label.draw()
    
    def _update_anim_dict(self, newdict):
        """Update the animation mappings with new values from <newdict>"""
        for k in ['at_rest', 'speaking']:
            if newdict.has_key(k):
                self.animations[k].update(newdict[k])
    
    def _reset_at_rest(self, exclude=None):
        """Set all involved actors to their resting positions"""
        for identifier, new_state in self.animations['at_rest'].viewitems():
            if identifier != exclude:
                self.scene.actors[identifier].update_state(new_state)
    
    def begin_conversation(self, convo_name):
        """Start a cutscene named <convo_name>"""
        self.convo_name = convo_name
        with pyglet.resource.file(self.scene.resource_path("convo/%s.convo" % convo_name), 'r') as f:
            self.convo_info = yaml.load(f)
            # Variables default to None
            self.convo_info['variables'] = nonedict(self.convo_info['variables'])
            self.animations = {
                'at_rest': {},
                'speaking': {}
            }
            # Add animations from YAML file
            self._update_anim_dict(self.convo_info)
            
            # Go!
            self.convo_lines = self.convo_info['start']
            self.convo_position = 0
            
            # Or not!
            if self.convo_info.has_key('stand_at'):
                def callback(*args):
                    self.scene.actors['main'].next_action()
                    self.next_line()
                self.scene.actors['main'].prepare_walkpath_move(self.convo_info['stand_at'],
                                                                callback=callback)
                self.scene.actors['main'].next_action()
            else:
                for identifier, new_state in self.animations['at_rest'].viewitems():
                    self.scene.actors[identifier].update_state(new_state)
                self.next_line()
    
    # ACTION LIST COMMANDS
    # Returns True if the caller can/should immediately execute the next line
    
    def _update_locals(self, val):
        """Update variables dictionary"""
        self.convo_info['variables'].update(val)
        return True
    
    def _update_globals(self, val):
        """Update variables dictionary"""
        self.scene.handler.handler.game_variables.update(val)
        return True
    
    def _play_sound(self, val):
        self.scene.play_sound(val)
        return True
    
    def _give(self, val):
        match = parens_match.match(val)
        if match:
            new_actor = actor.Actor(match.group('id'), match.group('name'), self.scene)
            # new_actor = self.scene.new_actor(match.group('name'), match.group('id'))
        else:
            next_identifier = 1
            while self.scene.actors.has_key("%s_%d" % (actor_name, next_identifier)):
                next_identifier += 1
            identifier = "%s_%d" % (actor_name, next_identifier)
            
            new_actor = actor.Actor(next_identifier, val, self.scene)
        
        self.scene.ui.inventory.put_item(new_actor)
        pyglet.resource.media('sound/give.wav').play()
        return True
    
    def _take(self, val):
        self.scene.ui.inventory.get_item(val)
        pyglet.resource.media('sound/take.wav').play()
        return True
    
    def _update_animations(self, val):
        """Update animations dictionary"""
        self._update_anim_dict(val)
        self._reset_at_rest()
        return True
    
    def _goto(self, val):
        """Start executing a different action list"""
        self.convo_position = 0
        if self.scene.ui.cam and not self.background:
            self.scene.ui.cam.set_visible(False)
        if val == 'exit':
            self.stop_speaking()
            return False
        else:
            self.convo_lines = self.convo_info[val]
            return True
    
    def _choice(self, val):
        """Present the user with a CAM where each button goes to a different label"""
        self.clear_speech_bubble()
        
        temp_choices = self._enforce_choice_requirements(val)
        choice_mappings = {k: self._make_choice_callback(k, val, v) for k, v
                           in temp_choices.viewitems()}
        self.scene.ui.show_cam(self.scene.actors['main'], choice_mappings)
        self.scene.ui.cam.hide_on_click_outside = False
        return False
    
    def _parse_command_dict(self, cmd_dict):
        """Search cmd_dict for actions to execute. Return True if caller should call next_line()."""
        needs_schedule = True
        for cmd, arg in cmd_dict.viewitems():
            try:
                result = getattr(self, '_%s' % cmd)(arg)
                needs_schedule = needs_schedule and result
            except AttributeError:
                pass    # Don't care, it's probably a spoken line
        return needs_schedule
    
    # CHOICE ACTION HELPERS
    
    def _make_choice_callback(self, choice, choice_dict, tag_dict):
        """Create a function to be called when a choice is clicked"""
        def decision():
            tags = nonedict(tag_dict)
            if tags['hide_after_use']:
                del choice_dict[choice]
            self._parse_command_dict(tags)
            if self.convo_lines:
                self.next_line()
            else:
                self.stop_speaking()
        return decision
    
    def _enforce_choice_requirements(self, choices):
        """Enforce 'requires' choice action"""
        temp_choices = choices.copy()
        for choice, tags in choices.viewitems():
            if tags.has_key('require'):
                v = self.convo_info['variables']
                for r in tags['require'].split(', '):
                    if not (r in v and v[r]) and not (r in self.scene.global_dict and self.scene.global_dict[r]) and not (r in self.scene.ui.inventory.items):
                        del temp_choices[choice]
                        break
        return temp_choices
    
    # OTHER CUTSCENE STUFF
    
    def next_line(self, dt=0):
        """Advance the cutscene by one line in the current action list"""
        # if not self.active:
        #     print 'Somehow we are trying to call next_line on an inactive conversation'
        #     return
        if self.convo_position >= len(self.convo_lines):
            self.stop_speaking()
        else:    
            line = self.convo_lines[self.convo_position]
            self.convo_position += 1
            needs_schedule = self._parse_command_dict(nonedict(line))
            for actor_id, arg in line.viewitems():
                if self.scene.actors.has_key(actor_id):
                    self.speak(actor_id, arg)
                    needs_schedule = False
            if needs_schedule:
                self.next_line()
    
    def speak(self, actor_id, arg):
        """Actor-specific actions like speaking and jumping"""
        if self.scene.ui.cam and not self.background:
            self.scene.ui.cam.set_visible(False)
        self._reset_at_rest(exclude=actor_id)
        act = self.scene.actors[actor_id]
        if isinstance(arg, str):
            act.update_state(self.animations['speaking'][actor_id])
            self.clear_speech_bubble()
            
            if not colors.has_key(actor_id):
                colors[actor_id] = more_colors.next()
            self.text_color = colors[actor_id]
            
            if len(arg) > 47:
                self.convo_label = pyglet.text.Label(arg, color=self.text_color, font_size=12, 
                                                     font_name=['Verdana', 'Helvetica'],
                                                     anchor_x='center', anchor_y='bottom',
                                                     x=act.sprite.x,
                                                     y=act.sprite.y + 20 + \
                                                        act.current_image().height - \
                                                        act.current_image().anchor_y,
                                                     multiline=True, width=multiline_w)
            else:
                self.convo_label = pyglet.text.Label(arg, color=self.text_color, font_size=12, 
                                                     font_name=['Verdana', 'Helvetica'],
                                                     anchor_x='center', anchor_y='bottom',
                                                     x=act.sprite.x,
                                                     y=act.sprite.y + 20 + \
                                                        act.current_image().height - \
                                                        act.current_image().anchor_y)
            
            self._update_vertices(act)
            self.scene.clock.schedule_once(self.next_line, max(len(arg)*0.05, 3.0))
            if not self.background:
                act.play_speaking_sound()
        else:
            if arg.has_key('action'):
                getattr(act, arg['action'])()
                self.next_line()
    
    def _update_vertices(self, act):
        offset_x, offset_y = act.dialogue_offset
        
        cw = self.convo_label.content_width/2+40
        self.convo_label.x = max(cw, self.convo_label.x)
        self.convo_label.x = min(self.scene.camera.position[0]+gamestate.norm_w/2-cw, self.convo_label.x)
        
        x = self.convo_label.x
        y = self.convo_label.y
        w = self.convo_label.content_width
        h = self.convo_label.content_height
        
        point_x = act.sprite.x + offset_x
        point_y = y + offset_y - 20
        
        if self.convo_label.multiline:
            x1, y1 = x - (multiline_w / 2) - 5, y - 5
            x2, y2 = x + (multiline_w / 2) + 5, y + h + 5
        else:
            x1, y1 = x - (w / 2) - 5,   y - 5
            x2, y2 = x + (w / 2) + 5,   y + h + 5
        
        first_tri = (x1, y1, x1, y2, x2, y2)
        if x1 <= point_x <= x2:
            point_left_x = max(point_x - 20 + offset_x*0.5, x1)
            point_left_y = y1
            point_right_x = min(point_x + 20 + offset_y*0.5, x2)
            point_right_y = y1
        
            last_tri = (point_right_x, point_right_y, point_x, point_y,
                        point_left_x, point_left_y)
        
            self.vertices_outline = first_tri + (x2, y1) + last_tri
            self.vertices_fill = first_tri + (x2, y2, x2, y1, x1, y1) + last_tri
        else:           
            mid_y = (y1 + y2) / 2                                           
            if point_x < x1:
                mid_x = x1 - 20
                self.vertices_outline = (x1, y1, mid_x, mid_y, x1, y2, x2, y2, x2, y1)
                self.vertices_fill = (x1, y1, mid_x, mid_y, x1, y2) + \
                                     first_tri + (x1, y1, x2, y2, x2, y1)
            elif point_x > x2:
                mid_x = x2 + 20
                self.vertices_outline = first_tri + (mid_x, mid_y, x2, y1)
                self.vertices_fill = first_tri + (x2, y2, x2, y1, x1, y1) + \
                                     (x2, y2, mid_x, mid_y, x2, y1)
    
    def clear_speech_bubble(self):
        """Clear all spoken text"""
        if self.convo_label:
            self.convo_label.delete()
            self.convo_label = None
    
    def stop_speaking(self, dt=0):
        """Stop the cutscene"""
        if not self.active:
            return
        self.clear_speech_bubble()
        self.scene.clock.unschedule(self.next_line)
        self.convo_lines = []
        
        for identifier, new_state in self.animations['at_rest'].viewitems():
            self.scene.actors[identifier].update_state(new_state)
        
        # Order matters here in case the script starts a new conversation
        cn = self.convo_name
        self.convo_name = None
        self.convo_info = None
        self.animations = None
        self.scene.call_if_available('end_conversation', cn)
    
