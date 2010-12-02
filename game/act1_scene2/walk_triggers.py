import functools
import pyglet
import re

from engine import actor
from engine.util import make_dt_wrapper

import state

@state.handles_walk('main')
def inga_walk(actor, point):
    if point == 'point_1':
        state.myscene.play_sound("door_open")
        state.myscene.handler.notify('act1_scene1')
    elif point == "point_2":
        if state.myscene.global_dict['groupies_blocked'] and \
        state.myscene.global_dict['potato_rolling']:
            state.myscene.begin_conversation("a_convenient_opening")
    elif point == "inga_attempt_stanislov":
        if not state.myscene.global_dict['guards_appeased']:
            mikhail = state.myscene.actors['mikhail']
            moritz = state.myscene.actors['moritz']
            if state.myscene.background_convo_in_progress("need_a_smoke"):
                state.myscene.end_background_conversation("need_a_smoke")
            mikhail.prepare_walkpath_move("mikhail_guard")
            moritz.prepare_walkpath_move("moritz_guard")
            mikhail.next_action()
            moritz.next_action()
            if not state.myscene.global_dict['no_groupies_intro']:
                state.myscene.begin_conversation("no_groupies_intro")
            else:
                state.myscene.begin_conversation("no_groupies")
    if point == "meet_stanislav" and 'kidnap_stanislav' in state.myscene.global_dict and state.myscene.global_dict['kidnap_stanislav']:
        kidnap_stanislav()
            
            
def kidnap_stanislav():
    blackout = actor.Actor('black', 'black', state.myscene)
    blackout.walkpath_point = 'blackout_p'
    state.myscene.add_actor(blackout)

@state.handles_walk('potato')
def potato_roll(actor, point):
    if point == "potato_15":
        state.myscene.interaction_enabled = True
    if point == "potato_9":
        state.myscene.actors['potato'].update_state("run_right")
        state.myscene.actors['potato'].prepare_walkpath_move("potato_15")
        state.myscene.actors['potato'].next_action()
        
@state.handles_walk('potato_drop')
def potato_drop(actor, point):
    if point == "potato_drop_end":
        #stanislav is surprised at the critter
        state.myscene.begin_conversation("a_visitor")
    
        actor.update_state('run_note_4')
 
    if point == "shake_4":
        actor.prepare_walkpath_move('potato_exit')
        pyglet.clock.schedule_once(make_dt_wrapper(actor.next_action), 3)
        actor.update_state('run_4')
