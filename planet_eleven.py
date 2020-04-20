import random
import math
import sys
import numpy as np
import win32api

from pyglet.sprite import Sprite
from pyglet.gl import *
from pyglet.window import key
from pyglet.window import mouse

from shadowandunittc import ShadowAndUnitTC
import resources as res
from weapons import *
from constants_and_utilities import *

lvb = 0
bvb = 0

POS_COORDS = []
g_pos_coord_d = {}
a_pos_coord_d = {}


def gen_pos_coords():
    """Generates a field of allowed positional coords. Declared as a function
    for resetting these."""
    global POS_COORDS, g_pos_coord_d, a_pos_coord_d
    POS_COORDS = []
    for yi in range(1, POS_COORDS_N_ROWS + 1):
        for xi in range(1, POS_COORDS_N_COLUMNS + 1):
            POS_COORDS.append((xi * PS - PS / 2,
                               yi * PS - PS / 2))
    g_pos_coord_d = {}
    for _x, _y in POS_COORDS:
        g_pos_coord_d[(_x, _y)] = None
    a_pos_coord_d = {}
    for _x, _y in POS_COORDS:
        a_pos_coord_d[(_x, _y)] = None


gen_pos_coords()


def to_minimap(x, y):  # unit.x and unit.y
    """Converts global coords into minimap coords. For positioning minimap
    pixels and camera."""
    x = x / PS
    if not x.is_integer():
        x += 1
    x = MM0X + x + lvb
    y = y / PS
    if not y.is_integer():
        y += 1
    y = MM0Y + y + bvb
    return x, y


def mc(**kwargs):
    """Modifies coords for different viewports. All clicks need this."""
    if len(kwargs) == 1:
        try:
            return kwargs['x'] + lvb
        except KeyError:
            return kwargs['y'] + bvb
    else:
        return kwargs['x'] + lvb, kwargs['y'] + bvb


def closest_enemy_2_att(entity, enemy_entities):
    closest_enemy = None
    closest_enemy_dist = None
    for enemy in enemy_entities:
        try:
            if not entity.attacks_air and enemy.flying:
                continue
            if not entity.attacks_ground and not enemy.flying:
                continue
        except AttributeError:
            pass
        dist_to_enemy = dist(enemy, entity)
        if dist_to_enemy <= entity.shooting_radius:
            if not closest_enemy:
                closest_enemy = enemy
                closest_enemy_dist = dist_to_enemy
            else:
                if dist_to_enemy < closest_enemy_dist:
                    closest_enemy = enemy
                    closest_enemy_dist = dist_to_enemy
    return closest_enemy


def update_shooting(game_inst, our_entities, enemy_entities):
    for entity in our_entities:
        try:  # For shooting structures
            entity.weapon_type
            entity.dest_reached
        except AttributeError:
            if entity.under_constr:
                return
            entity.weapon_type = 'projectile'
            entity.dest_reached = True
        if entity.weapon_type != 'none' and entity.dest_reached:
            if not entity.on_cooldown:
                if not entity.has_target_p:
                    closest_enemy = closest_enemy_2_att(entity,
                                                        enemy_entities)
                    if closest_enemy:
                        entity.has_target_p = True
                        entity.target_p = closest_enemy
                        entity.target_p_x = closest_enemy.x
                        entity.target_p_y = closest_enemy.y
                        entity.target_p.attackers.append(entity)
                # Has target_p
                elif dist(entity, entity.target_p) <= entity.shooting_radius:
                    entity.shoot(game_inst.f)
                else:
                    entity.has_target_p = False
                    entity.target_p.attackers.remove(entity)
                    entity.target_p = None
                    entity.target_p_x = None
                    entity.target_p_y = None
            else:
                if (game_inst.f - entity.cooldown_started) % \
                        entity.cooldown == 0:
                    entity.on_cooldown = False


class UI(Sprite):
    """This class is used for UI elements that need to be relocated when
    a player moves the viewport."""
    def __init__(self, game_inst, img, x, y, batch=None):
        super().__init__(img, x, y, batch=batch)
        self.org_x = x
        self.org_y = y
        game_inst.ui.append(self)

class CheckB(Sprite):
    """Check buttons."""
    def __init__(self, game_inst, x, y, checked=True):
        super().__init__(res.check_b, x, y, batch=options_batch)
        self.org_x = x
        self.org_y = y
        game_inst.ui.append(self)
        self.check = UI(game_inst, res.check, x, y, batch=check_batch)
        if checked == False:
            self.check.visible = False

class Player:
    def __init__(self, name):
        self.min_c = 5000
        self.name = name

class HitAnim(Sprite):
    def __init__(self, x, y):
        super().__init__(res.hit_anim, x, y, batch=explosions_batch)

class Explosion(Sprite):
    def __init__(self, x, y, scale=1):
        super().__init__(res.explosion_anim, x, y, batch=explosions_batch)
        self.scale = scale

class Mineral(Sprite):
    def __init__(self, outer_instance, x, y, hp=5000):
        super().__init__(img=res.mineral, x=x, y=y, batch=structures_batch)
        self.outer_instance = outer_instance
        self.workers = []
        self.hp = hp
        self.cbs = None
        self.icon = res.mineral
        minerals.append(self)
        g_pos_coord_d[(x, y)] = self

    def kill(self):
        for worker in self.workers:
            worker.clear_task()
            worker.stop_move()
        g_pos_coord_d[(self.x, self.y)] = None
        self.delete()


def order_unit(game_inst, struct, unit):
    """Orders units in structures. Checks if you have enough minerals."""
    owner = struct.owner
    # Queue is full
    if len(struct.prod_q) == 3:
        if owner == game_inst.this_player:
            game_inst.txt_out.text = "Queue is full"
            game_inst.txt_out_upd_f = game_inst.f
        return
    # Enough minerals
    if owner.min_c - unit.cost >= 0:
        owner.min_c -= unit.cost
        game_inst.update_min_c_label()
        struct.prod_q.append(unit)
        struct.anim.visible = True
        struct.prod_complete = False
        if selected == struct:
            game_inst.prod_bar_bg.visible = True
            game_inst.prod_bar.visible = True
            if len(struct.prod_q) == 1:
                struct.prod_start_f = game_inst.f
                game_inst.prod_icon1.image = unit.icon
            elif len(struct.prod_q) == 2:
                game_inst.prod_icon2.image = unit.icon
            else:
                game_inst.prod_icon3.image = unit.icon
    # Not enough minerals
    else:
        if owner == game_inst.this_player:
            game_inst.txt_out.text = "Not enough minerals"
            game_inst.txt_out_upd_f = game_inst.f


def building_spawn_unit(game_inst, struct):
    if struct.prod_q:
        unit = struct.prod_q[0]
        struct.cur_max_prod_time = unit.build_time
        # Is it time to spawn?
        if game_inst.f - struct.prod_start_f >= struct.cur_max_prod_time:
            if str(struct.prod_q[0]) not in LIST_OF_FLYING:
                dict_to_check = g_pos_coord_d
            else:
                dict_to_check = a_pos_coord_d
            # Searching for a place to build
            if struct.width == PS:
                x = struct.x - PS
                y = struct.y - PS
            else:
                x = struct.x - PS * 1.5
                y = struct.y - PS * 1.5
            org_x = x
            org_y = y
            place_found = False
            n = struct.width // PS + 2
            for i in range(n):
                x = org_x + PS * i
                if dict_to_check[(x, y)] is None:
                    place_found = True
                    break
            for i in range(n):
                y = org_y + PS * i
                if dict_to_check[(x, y)] is None:
                    place_found = True
                    break
            org_x = x
            for i in range(n):
                x = org_x - PS * i
                if dict_to_check[(x, y)] is None:
                    place_found = True
                    break
            org_y = y
            for i in range(n):
                y = org_y - PS * i
                if dict_to_check[(x, y)] is None:
                    place_found = True
                    break
            if place_found:
                unit = struct.prod_q.pop(0)
                unit = unit(game_inst, x=x, y=y, owner=struct.owner)
                unit.spawn()
                struct.prod_start_f += struct.cur_max_prod_time
                if not struct.prod_q:
                    struct.anim.visible = False
                if not struct.default_rp:
                    unit.move((struct.rp_x, struct.rp_y))
                if struct.owner == game_inst.this_player:
                    game_inst.prod_icon1.image = game_inst.prod_icon2.image
                    game_inst.prod_icon2.image = game_inst.prod_icon3.image
                    game_inst.prod_icon3.image = res.none_img
            else:
                struct.prod_start_f += 1
                if struct.owner == game_inst.this_player:
                    game_inst.txt_out.text = "No place"
                    game_inst.txt_out_upd_f = game_inst.f


def order_structure(game_inst, unit, struct, x, y):
    owner = unit.owner
    if owner.min_c - struct.cost >= 0:
        owner.min_c -= struct.cost
        game_inst.update_min_c_label()
        unit.to_build = game_inst.to_build
        unit.task_x = game_inst.to_build_spt.x
        unit.task_y = game_inst.to_build_spt.y
        unit.move((x, y))
    else:
        if owner == game_inst.this_player:
            game_inst.txt_out.text = "Not enough minerals"
            game_inst.txt_out_upd_f = game_inst.f


class Struct(Sprite):
    """This is what I call buildings. __init__ == spawn()"""

    def __init__(self, game_inst, owner, img, team_color_img, icon, vision_radius,
                 hp, x, y):
        self.owner = owner
        self.team_color = Sprite(team_color_img, x, y,
                                 batch=ground_team_color_batch)
        self.team_color.visible = False
        self.icon = icon
        if owner == game_inst.this_player:
            self.team_color.color = OUR_TEAM_COLOR
            our_structs.append(self)
            minimap_pixel = res.mm_our_img
            game_inst.update_fow(x=x, y=y, radius=vision_radius)
        else:
            self.team_color.color = ENEMY_TEAM_COLOR
            enemy_structs.append(self)
            minimap_pixel = res.mm_enemy_img
        super().__init__(img, x, y, batch=structures_batch)
        self.completed_image = img
        self.game_inst = game_inst
        self.max_hp = hp
        self.hp = hp
        if self.width / 32 % 2 == 1:
            d = self.width / PS // 2 * PS
            n = self.width // PS
            width = 1
        else:
            n = int(self.width / PS // 2)
            d = self.width / PS // 2 * PS - PS / 2
            width = 2
        # print('d =', d, 'n =', n, 'width =', width)
        x -= d
        y -= d
        self.blocks = [(x, y)]
        for _ in range(n):
            for _ in range(width):
                self.blocks.append((x, y))
                g_pos_coord_d[(x, y)] = self
                x += PS
            x -= PS
            for _ in range(width - 1):
                y += PS
                self.blocks.append((x, y))
                g_pos_coord_d[(x, y)] = self
            for _ in range(width - 1):
                x -= PS
                self.blocks.append((x, y))
                g_pos_coord_d[(x, y)] = self
            for _ in range(width - 2):
                self.blocks.append((x, y))
                g_pos_coord_d[(x, y)] = self
                y -= PS
            width += 2
        if self.owner == game_inst.this_player:
            for block in self.blocks:
                game_inst.update_fow(x=block[0], y=block[1],
                                     radius=vision_radius)
        self.default_rp = True
        self.attackers = []

        pixel_minimap_coords = to_minimap(self.x, self.y)
        self.pixel = Sprite(img=minimap_pixel,
                            x=pixel_minimap_coords[0],
                            y=pixel_minimap_coords[1],
                            batch=minimap_pixels_batch)

    def kill(self, delay_del=False):
        global our_structs, enemy_structs
        for block in self.blocks:
            g_pos_coord_d[(block[0], block[1])] = None
        self.team_color.delete()
        self.pixel.delete()
        if not delay_del:
            for arr in (our_structs, enemy_structs, prod_structs):
                try:
                    arr.remove(self)
                except ValueError:
                    pass
        for attacker in self.attackers:
            attacker.has_target_p = False
        try:
            self.anim.delete()
        except AttributeError:
            pass
        Explosion(self.x, self.y, self.width / PS / 2)
        self.delete()

    def constr_complete(self):
        self.under_constr = False
        self.image = self.completed_image
        self.team_color.visible = True


class ProductionStruct:
    def ps_init(self):
        prod_structs.append(self)
        self.rp_x = self.x
        self.rp_y = self.y
        self.prod_q = []
        self.cur_max_prod_time = None
        self.prod_complete = True
        self.prod_start_f = 0


class GuardianStructure:
    def gs_init(self, skip_constr):
        if not skip_constr:
            guardian_dummies.append(self)
            self.image = res.constr_dummy_anim
            self.const_f = self.game_inst.f
            self.under_constr = True
        else:
            self.constr_complete()


class Armory(Struct, GuardianStructure):
    cost = 200
    build_time = 60

    def __init__(self, game_inst, x, y, owner=None, skip_constr=False):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.armory_img,
                         res.armory_team_color, res.armory_icon_img,
                         vision_radius=2,  hp=100, x=x, y=y)
        super().gs_init(skip_constr)


class MechCenter(Struct, ProductionStruct, GuardianStructure):
    cost = 500
    build_time = 100

    def __init__(self, game_inst, x, y, owner=None, skip_constr=False):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.mech_center_img,
                         res.mech_center_team_color, res.mech_center_icon_img,
                         x=x, y=y, hp=1500, vision_radius=4)
        super().ps_init()
        super().gs_init(skip_constr)
        self.cbs = [game_inst.defiler_b, game_inst.centurion_b,
                    game_inst.wyrm_b, game_inst.apocalypse_b,
                    game_inst.pioneer_b, game_inst.cancel_b]
        self.is_big = True
        if owner.name == 'player1':
            self.anim = Sprite(img=res.anim, x=x, y=y, batch=ground_units_batch)
        else:
            self.anim = Sprite(img=res.anim_enemy, x=x, y=y,
                               batch=ground_units_batch)
        self.anim.visible = False


class OffensiveStruct(Struct):
    def __init__(self, game_inst, owner, img, team_color, icon, vision_radius, hp,
                 x, y, damage, cooldown):
        super().__init__(game_inst, owner, img, team_color, icon, vision_radius,
                         hp, x, y)
        self.damage = damage
        self.shooting_radius = vision_radius * 32
        self.target_x = None
        self.target_y = None
        self.cooldown = cooldown
        self.on_cooldown = False
        self.cooldown_started = None
        offensive_structs.append(self)
        self.projectile_sprite = res.laser_img
        self.projectile_speed = 5
        self.has_target_p = False
        self.target_p = None
        self.target_p_x = None
        self.target_p_y = None

    def shoot(self, f):
        global projectiles
        projectile = Projectile(self.x, self.y, self.target_p.x,
                                self.target_p.y, self.damage,
                                self.projectile_speed, self.target_p,
                                res.plasma_anim)
        x_diff = self.target_p.x - self.x
        y_diff = self.target_p.y - self.y
        self.on_cooldown = True
        self.cooldown_started = f
        projectiles.append(projectile)

    def kill(self, delay_del=False):
        global g_pos_coord_d, our_structs, enemy_structs
        g_pos_coord_d[(self.x, self.y)] = None
        self.pixel.delete()
        for attacker in self.attackers:
            attacker.has_target_p = False
        if not delay_del:
            if self.owner.name == 'player1':
                del our_structs[our_structs.index(self)]
            else:
                del enemy_structs[enemy_structs.index(self)]
        del offensive_structs[offensive_structs.index(self)]
        self.plasma_spt.delete()
        self.team_color.delete()
        Explosion(self.x, self.y, self.width / PS / 2)
        self.delete()


class Turret(OffensiveStruct, GuardianStructure):
    cost = 150
    build_time = 40

    def __init__(self, game_inst, x, y, owner=None, skip_constr=False):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.turret_img,
                         res.turret_team_color, res.turret_icon_img,
                         vision_radius=5,
                         hp=100, x=x, y=y, damage=20, cooldown=60)
        super().gs_init(skip_constr)

    def constr_complete(self):
        self.under_constr = False
        self.image = self.completed_image
        self.team_color.visible = True

        self.plasma_spt = Sprite(res.plasma_anim, self.x, self.y,
                                 batch=ground_units_batch)


node_count = 0


def astar(map, start, end, acc_ends):
    """A* pathfinding. acc_ends are other acceptable end coords that are used
    when we cannot reach the exact end."""
    global node_count

    class Node:
        def __init__(self, parent=None, pos=None):
            global node_count
            node_count += 1
            self.parent = parent
            self.pos = pos
            self.g = 0
            self.f = 0

        def __eq__(self, other):
            return self.pos == other.pos

    # Create start, end, and acc_ends nodes
    start_node = Node(None, start)
    start_node.g = start_node.f = 0
    end_node = Node(None, end)
    end_node.g = end_node.f = 0
    # print(acc_ends)
    acc_end_nodes = []
    for acc_end in acc_ends:
        # print(acc_end)
        acc_end_nodes.append(Node(None, acc_end))
    # open_list is where you can go now
    open_list = [start_node]
    # closed_list is where we already were
    closed_list = []

    max_nodes = ((start[0] + end[0]) ** 2 + (
            start[1] + end[1]) ** 2) ** 0.5 * 7

    # Loop until you find the end
    while len(open_list) > 0:
        # Get the current node. Which is the node with lowest f of the entire
        # open_list
        current_node = open_list[0]
        current_index = 0
        for index, item in enumerate(open_list):
            if item.f < current_node.f:
                current_node = item
                current_index = index

        # Pop current off open_list, add to closed list
        closed_list.append(open_list.pop(current_index))

        if node_count > max_nodes:
            node_count = 0
            return []

        # Return path
        # print("current_node.pos =", current_node.pos)
        for node in acc_end_nodes:
            # print("node.pos =", node.pos)
            if node == current_node:
                # print(1)
                path = []
                while current_node:
                    path.append(current_node.pos)
                    current_node = current_node.parent
                # print(2)
                node_count = 0
                return path[::-1]  # Return reversed path

        # Generate children
        children = []
        for new_pos in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1),
                        (1, -1), (1, 1)]:  # Adjacent squares

            # Get node position
            node_pos = (
                current_node.pos[0] + new_pos[0],
                current_node.pos[1] + new_pos[1])

            # Make sure within range
            if node_pos[0] > len(map[0]) - 1 or node_pos[0] < 0 \
                    or node_pos[1] > len(map) - 1 or node_pos[1] < 0:
                continue

            # Make sure walkable terrain
            if map[node_pos[1]][node_pos[0]] != 0:
                continue

            # Create new node
            new_node = Node(current_node, node_pos)

            # Append
            children.append(new_node)

        # Loop through children
        for child in children:

            # Child is already in the open list
            if child in open_list:
                continue

            # Child is on the closed list
            if child in closed_list:
                continue

            # Create the f, g, and h values
            child.g = current_node.g + 1
            child.f = child.g + (child.pos[0] - end_node.pos[0]) ** 2 + (
                    child.pos[1] - end_node.pos[1]) ** 2

            # Add the child to the open list
            open_list.append(child)


def convert_map(pos_coords_dict):
    """Converts the map for path-finding."""
    new_map = []
    i = 1
    row = []
    for x, y in POS_COORDS:
        if pos_coords_dict[(x, y)]:
            row.append(1)
        else:
            row.append(0)
        if i % 100 == 0:
            new_map.append(row)
            row = []
        i += 1
    return new_map


def convert_c_to_simple(c):
    """Called by find_path() only."""
    return int((c - PS // 2) // PS)


def find_path(start, end, is_flying):
    """Main path-finding function. Calls other PF functions."""
    # print('start =', start, 'end =', end)
    # Check end neighbors
    if not is_flying:
        selected_dict = g_pos_coord_d
    else:
        selected_dict = a_pos_coord_d
    if selected_dict[(end[0], end[1])] is None:
        acc_ends = [(convert_c_to_simple(end[0]), convert_c_to_simple(end[1]))]
    else:
        width = 3
        while True:
            acc_ends = []
            dx = dy = -PS
            for i in range(width):
                coord = (end[0] + dx, end[1] + dy)
                try:
                    if selected_dict[coord] is None:
                        acc_ends.append((convert_c_to_simple(coord[0]),
                                         convert_c_to_simple(coord[1])))
                except KeyError:  # Out of the map borders
                    pass
                dx += PS
            dx -= PS
            for i in range(width - 1):
                dy += PS
                coord = (end[0] + dx, end[1] + dy)
                try:
                    if selected_dict[coord] is None:
                        acc_ends.append((convert_c_to_simple(coord[0]),
                                         convert_c_to_simple(coord[1])))
                except KeyError:  # Out of the map borders
                    pass
            for i in range(width - 1):
                dx -= PS
                coord = (end[0] + dx, end[1] + dy)
                try:
                    if selected_dict[coord] is None:
                        acc_ends.append((convert_c_to_simple(coord[0]),
                                         convert_c_to_simple(coord[1])))
                except KeyError:  # Out of the map borders
                    pass
            for i in range(width - 2):
                dy -= PS
                coord = (end[0] + dx, end[1] + dy)
                try:
                    if selected_dict[coord] is None:
                        acc_ends.append((convert_c_to_simple(coord[0]),
                                         convert_c_to_simple(coord[1])))
                except KeyError:  # Out of the map borders
                    pass
            if acc_ends:
                break
            width += 1
    # print("acc_ends =", acc_ends)
    start = convert_c_to_simple(start[0]), convert_c_to_simple(start[1])
    end = convert_c_to_simple(end[0]), convert_c_to_simple(end[1])
    # print('start =', start, 'end =', end)
    map = convert_map(selected_dict)
    # print('map converted to simple')
    map[start[1]][start[0]] = 0
    map[end[1]][end[0]] = 0
    path = astar(map, start, end, acc_ends)
    # print('path =', path)
    if not path:
        return []
    converted_path = []
    for x, y in path:
        x = x * PS + PS // 2
        y = y * PS + PS // 2
        converted_path.append((x, y))
    # print('converted_path =', converted_path)
    return converted_path


class Unit(Sprite):
    def __init__(self, game_inst, owner, img, team_color_img, icon, flying,
                 vision_radius, hp, x, y, speed, weapon_type, damage, cooldown,
                 attacks_ground, attacks_air, shadow_sprite, cbs):
        self.game_inst = game_inst
        self.owner = owner
        self.team_color = ShadowAndUnitTC(team_color_img, x, y,
                                          ground_team_color_batch)
        self.icon = icon
        if owner.name == 'player1':
            self.team_color.color = OUR_TEAM_COLOR
            our_units.append(self)
        else:
            self.team_color.color = ENEMY_TEAM_COLOR
            enemy_units.append(self)
        self.flying = flying
        if not self.flying:
            self.pos_dict = g_pos_coord_d
            batch = ground_units_batch
        else:
            self.pos_dict = a_pos_coord_d
            batch = air_batch
            self.team_color.batch = air_team_color_batch
        super().__init__(img, x, y, batch=batch)
        self.vision_radius = vision_radius
        self.attacks_ground = attacks_ground
        self.attacks_air = attacks_air
        self.max_hp = hp
        self.hp = hp
        self.x = x
        self.y = y
        self.speed = speed
        self.weapon_type = weapon_type
        self.damage = damage
        self.cooldown = cooldown
        self.attacks_ground = attacks_ground
        self.attacks_air = attacks_air
        self.shooting_radius = vision_radius * 32
        self.shadow_sprite = shadow_sprite
        self.cbs = cbs

        self.dest_reached = True
        self.move_interd = False
        self.target_x = x
        self.target_y = y
        self.dest_x = None
        self.dest_y = None
        self.velocity_x = 0
        self.velocity_y = 0
        self.has_target_p = False
        self.target_p = None
        self.target_p_x = None
        self.target_p_y = None
        self.on_cooldown = False
        self.cooldown_started = None
        self.attackers = []
        self.attack_moving = False

    def spawn(self):
        """Creates a unit at it's predefined self.x and self.y. Does not move
        it to the rally point."""
        self.pos_dict[(self.x, self.y)] = self

        # Minimap pixel and fow
        pixel_minimap_coords = to_minimap(self.x, self.y)
        if self.owner.name == 'player1':
            pixel = res.mm_our_img
            self.game_inst.update_fow(self.x, self.y, self.vision_radius)
        else:
            pixel = res.mm_enemy_img
        self.pixel = Sprite(img=pixel, x=pixel_minimap_coords[0],
                            y=pixel_minimap_coords[1],
                            batch=minimap_pixels_batch)

        # Shadow
        if self.flying:
            self.shadow = ShadowAndUnitTC(img=self.shadow_sprite, x=self.x + 10,
                                          y=self.y - 10)
            self.shadow.batch = air_shadows_batch
        else:
            self.shadow = ShadowAndUnitTC(img=self.shadow_sprite, x=self.x + 3,
                                          y=self.y - 3)
            self.shadow.batch = ground_shadows_batch

    def update(self):
        """Updates position and shadow."""
        self.x, self.y = self.x + self.velocity_x, self.y + self.velocity_y
        self.team_color.update()
        self.shadow.update()

    def rotate(self, x, y):
        """Rotates a unit in the direction of his task(mining, building,
        etc.)"""
        diff_x = x - self.x
        diff_y = y - self.y
        angle = math.atan2(diff_y, diff_x)  # Rad
        self.rotation = -math.degrees(angle) + 90
        self.team_color.rotation = -math.degrees(angle) + 90
        self.shadow.rotation = -math.degrees(angle) + 90

    def move(self, dest):
        """Called once by RMB or when a unit is created by a building with
        a non-default rally point."""
        if self.attack_moving:  # Will not work for computer
            if self.owner.name == 'player1':
                if closest_enemy_2_att(self, enemy_units + enemy_structs):
                    self.attack_moving = False
                    self.dest_reached = True
                    return
            else:
                if closest_enemy_2_att(self, our_units + our_structs):
                    self.attack_moving = False
                    self.dest_reached = True
                    return
        # Not moving: same coords
        if self.x == dest[0] and self.y == dest[1]:
            self.dest_reached = True
            return

        # Not moving: melee distance and dest occupied
        if is_melee_dist(self, dest[0], dest[1]) and \
                self.pos_dict[(dest[0], dest[1])]:
            self.dest_reached = True
            return
        # Moving or just rotating
        self.dest_reached = False
        self.dest_x, self.dest_y = dest[0], dest[1]

        self.pfi = 1  # 0 creates a bug of rotating to math degree of 0
        # because the 0 element in path is the starting location
        self.path = find_path((self.x, self.y), (self.dest_x, self.dest_y),
                              self.flying)
        try:
            target = self.path[self.pfi]
        except IndexError:
            self.dest_reached = True
            return
        if target:  # If we can reach there
            # print('target =', target)
            self.target_x = target[0]
            self.target_y = target[1]
            self.pixel.x, self.pixel.y = to_minimap(self.target_x,
                                                    self.target_y)
        # Not moving
        else:
            self.dest_reached = True
            self.pos_dict[(self.x, self.y)] = self
            return
        diff_x = self.target_x - self.x
        diff_y = self.target_y - self.y
        angle = math.atan2(diff_y, diff_x)  # Rad
        self.rotation = -math.degrees(angle) + 90
        self.velocity_x = math.cos(angle) * self.speed
        self.velocity_y = math.sin(angle) * self.speed
        self.team_color.rotation = -math.degrees(angle) + 90
        self.team_color.velocity_x = math.cos(angle) * self.speed
        self.team_color.velocity_y = math.sin(angle) * self.speed
        self.shadow.rotation = -math.degrees(angle) + 90
        self.shadow.velocity_x = math.cos(angle) * self.speed
        self.shadow.velocity_y = math.sin(angle) * self.speed
        self.pos_dict[(self.x, self.y)] = None
        self.pos_dict[(self.target_x, self.target_y)] = self

    def eta(self):
        """Estimated time of arrival to the target location (not dest)."""
        dist_to_target = ((self.target_x - self.x) ** 2 + (
                self.target_y - self.y) ** 2) ** 0.5
        return dist_to_target / self.speed

    def update_move(self):
        """Called by update to move to the next point."""
        self.pfi += 1
        diff_x = self.dest_x - self.x
        diff_y = self.dest_y - self.y
        angle = math.atan2(diff_y, diff_x)  # Rad
        d_angle = math.degrees(angle)
        self.rotation = -d_angle + 90
        self.team_color.rotation = -math.degrees(angle) + 90
        self.shadow.rotation = -math.degrees(angle) + 90
        try:
            next_target = self.path[self.pfi]
        except IndexError:
            self.dest_reached = True
            return
        if self.pos_dict[
            (next_target[0], next_target[1])]:  # Obstruction detected
            self.move((self.dest_x, self.dest_y))
            return
        if next_target:  # Moving
            self.pos_dict[(self.x, self.y)] = None
            self.target_x = next_target[0]
            self.target_y = next_target[1]
            self.pixel.x, self.pixel.y = to_minimap(self.target_x,
                                                    self.target_y)
            self.pos_dict[(self.target_x, self.target_y)] = self
            diff_x = self.target_x - self.x
            diff_y = self.target_y - self.y
            angle = math.atan2(diff_y, diff_x)  # Rad
            d_angle = math.degrees(angle)
            self.rotation = -d_angle + 90
            self.velocity_x = math.cos(angle) * self.speed
            self.velocity_y = math.sin(angle) * self.speed
            self.team_color.rotation = -math.degrees(angle) + 90
            self.team_color.velocity_x = math.cos(angle) * self.speed
            self.team_color.velocity_y = math.sin(angle) * self.speed
            self.shadow.rotation = -math.degrees(angle) + 90
            self.shadow.velocity_x = math.cos(angle) * self.speed
            self.shadow.velocity_y = math.sin(angle) * self.speed
        else:
            self.pos_dict[(self.x, self.y)] = self
            self.dest_reached = True

    def shoot(self, f):
        if self.weapon_type == 'projectile':
            projectile = Projectile(x=self.x, y=self.y, target_x=self.target_p.x,
                                    target_y=self.target_p.y, damage=self.damage,
                                    speed=10, target_obj=self.target_p)
            projectiles.append(projectile)
        elif self.weapon_type == 'bomb':
            bomb = Bomb(x=self.x, y=self.y, target_x=self.target_p.x,
                        target_y=self.target_p.y, damage=self.damage,
                        speed=2)
            bombs.append(bomb)
        else:  # Zap
            self.target_p.hp -= self.damage
            Zap(self.x, self.y, self.target_p.x, self.target_p.y,
                self.game_inst.f)
            HitAnim(self.target_p.x, self.target_p.y)
        x_diff = self.target_p.x - self.x
        y_diff = self.target_p.y - self.y
        angle = -math.degrees(math.atan2(y_diff, x_diff)) + 90
        self.rotation = angle
        self.team_color.rotation = angle
        self.shadow.rotation = angle
        self.on_cooldown = True
        self.cooldown_started = f


    def stop_move(self):
        """Stops movement."""
        if not self.dest_reached:
            self.dest_x = self.target_x
            self.dest_y = self.target_y

    def kill(self, delay_del=False):
        self.pixel.delete()
        self.team_color.delete()
        self.shadow.delete()
        for attacker in self.attackers:
            attacker.has_target_p = False
        if not delay_del:
            if self.owner.name == 'player1':
                del our_units[our_units.index(self)]
            else:
                del enemy_units[enemy_units.index(self)]
        self.pos_dict[(self.target_x, self.target_y)] = None
        Explosion(self.x, self.y, 0.25)
        self.delete()
        try:
            del workers[workers.index(self)]
            self.zap_sprite.delete()
        except ValueError:
            pass


class Apocalypse(Unit):
    cost = 600
    build_time = 100
    icon = res.apocalypse_icon_img

    def __init__(self, game_inst, x, y, owner=None):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.apocalypse_img,
                         res.apocalypse_team_color, res.apocalypse_icon_img,
                         flying=True,
                         vision_radius=6, hp=100, x=x, y=y, speed=1,
                         weapon_type='projectile', damage=100, cooldown=200,
                         attacks_ground=True, attacks_air=False,
                         shadow_sprite=res.apocalypse_shadow_img,
                         cbs=game_inst.basic_unit_c_bs)


class Centurion(Unit):
    cost = 400
    build_time = 100
    icon = res.centurion_icon_img

    def __init__(self, game_inst, x, y, owner=None):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.centurion_img,
                         res.centurion_team_color, res.centurion_icon_img,
                         flying=False,
                         vision_radius=6, hp=100, x=x, y=y, speed=1,
                         weapon_type='projectile', damage=10, cooldown=120,
                         attacks_ground=True, attacks_air=False,
                         shadow_sprite=res.centurion_shadow_img,
                         cbs=game_inst.basic_unit_c_bs)


class Defiler(Unit):
    cost = 300
    build_time = 100
    icon = res.defiler_icon_img

    def __init__(self, game_inst, x, y, owner=None):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.defiler_img,
                         res.defiler_team_color, res.defiler_icon_img,
                         flying=True,
                         vision_radius=6, hp=70, x=x, y=y, speed=3,
                         weapon_type='instant', damage=10, cooldown=60,
                         attacks_ground=True, attacks_air=True,
                         shadow_sprite=res.defiler_shadow_img,
                         cbs=game_inst.basic_unit_c_bs)


class Pioneer(Unit):
    cost = 50
    build_time = 50
    icon = res.pioneer_icon_img

    def __init__(self, game_inst, x, y, owner=None):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.pioneer_img,
                         res.pioneer_team_color, res.pioneer_icon_img,
                         flying=False,
                         vision_radius=4, hp=10, x=x, y=y, speed=2,
                         weapon_type='none', damage=0, cooldown=0,
                         attacks_ground=False, attacks_air=False,
                         shadow_sprite=res.pioneer_shadow_img,
                         cbs=game_inst.basic_unit_c_bs +
                                      [game_inst.armory_icon] +
                                      [game_inst.turret_icon] +
                                      [game_inst.mech_center_icon])
        workers.append(self)
        self.to_build = None
        self.mineral_to_gather = None
        self.task_x = None
        self.task_y = None
        self.is_gathering = False
        self.zap_sprite = Sprite(res.zap_anim, self.x, self.y,
                                 batch=weapons_batch)
        self.zap_sprite.visible = False

    def build(self):
        self.mineral_to_gather = None
        self.is_gathering = False
        self.zap_sprite.visible = False
        self.dest_reached = True
        g_pos_coord_d[(self.target_x, self.target_y)] = None
        g_pos_coord_d[(self.x, self.y)] = self
        if self.to_build == "armory":
            if not g_pos_coord_d[(self.task_x, self.task_y)]:
                Armory(self.game_inst, self.task_x, self.task_y)
            else:
                self.owner.min_c += Armory.cost
        elif self.to_build == "turret":
            if not g_pos_coord_d[(self.task_x, self.task_y)]:
                Turret(self.game_inst, self.task_x, self.task_y)
            else:
                self.owner.min_c += Turret.cost
        elif self.to_build == "mech_center":
            x = self.task_x - PS / 2
            y = self.task_y - PS / 2
            coords_to_check = [(x, y), (x + PS, y), (x + PS, y + PS),
                               (x, y + PS)]
            no_place = False
            for c in coords_to_check:
                if g_pos_coord_d[(c[0], c[1])]:
                    no_place = True
                    break
            if no_place is False:
                MechCenter(self.game_inst, self.task_x, self.task_y)
            else:
                self.owner.min_c += MechCenter.cost
        self.to_build = None

    def gather(self):
        self.rotate(self.mineral_to_gather.x, self.mineral_to_gather.y)
        self.is_gathering = True
        self.zap_sprite.x = self.x
        self.zap_sprite.y = self.y
        diff_x = self.task_x - self.x
        diff_y = self.task_y - self.y
        _dist = (diff_x ** 2 + diff_y ** 2) ** 0.5
        self.zap_sprite.scale_x = _dist / PS
        angle = math.atan2(diff_y, diff_x)  # Rad
        self.zap_sprite.rotation = -math.degrees(angle)
        self.zap_sprite.visible = True
        self.cycle_started = self.game_inst.f

    def clear_task(self):
        self.to_build = None
        self.mineral_to_gather = None
        self.task_x = None
        self.task_y = None
        self.is_gathering = False
        self.zap_sprite.visible = False


class Wyrm(Unit):
    cost = 150
    build_time = 50
    icon = res.wyrm_icon_img

    def __init__(self, game_inst, x, y, owner=None):
        if owner is None:
            owner = game_inst.this_player
        super().__init__(game_inst, owner, res.wyrm_img,
                         res.wyrm_team_color, res.wyrm_icon_img, flying=False,
                         vision_radius=3, hp=25, x=x, y=y, speed=3,
                         weapon_type='projectile', damage=5, cooldown=60,
                         attacks_ground=True, attacks_air=False,
                         shadow_sprite=res.wyrm_shadow_img,
                         cbs=game_inst.basic_unit_c_bs)


class PlanetEleven(pyglet.window.Window):
    def __init__(self, width, height, title):
        conf = Config(sample_buffers=1, samples=4, depth_size=16,
                      double_buffer=True)
        super().__init__(width, height, title, config=conf)
        self.set_mouse_cursor(res.cursor)
        self.show_fps = False
        self.fps_display = pyglet.window.FPSDisplay(window=self)
        self.ui = []
        self.mouse_x = 0
        self.mouse_y = 0
        self.show_hint = False
        self.menu_bg = UI(self, res.menu_bg, 0, 0)

    def setup(self):
        global selected
        self.paused = False
        self.options = False
        self.f = 0
        self.this_player = Player("player1")
        self.computer = Player("computer1")
        self.computer.min_c = 50000
        self.computer.workers_count = 0
        self.dx = 0
        self.dy = 0
        self.minimap_drugging = False
        self.build_loc_sel_phase = False
        self.m_targeting_phase = False
        self.targeting_phase = False

        self.terrain = Sprite(img=res.terrain_img, x=0, y=0)
        self.cp_spt = UI(self, res.cp_img, SCREEN_W, 0)
        self.menu_b = UI(self, res.menu_img, cp_c_x, SCREEN_H - 30)
        self.sel_frame_cp = UI(self, res.sel_frame_img, cp_c_x, SCREEN_H - 90)
        self.cp_b_bg = UI(self, res.cp_buttons_bg_img, cp_c_x, cp_c_y)
        self.mm_textured_bg = UI(self, res.mm_textured_bg_img, MM0X, MM0Y)
        self.mm_cam_frame_spt = Sprite(res.mm_cam_frame_img, MM0X - 1,
                                       MM0Y - 1)
        self.mm_fow_img = pyglet.image.load('sprites/mm/mm_fow.png')
        self.mm_fow_ImageData = self.mm_fow_img.get_image_data()
        self.npa = np.fromstring(self.mm_fow_ImageData.get_data(
            'RGBA', self.mm_fow_ImageData.width * 4), dtype=np.uint8)
        self.npa = self.npa.reshape((102, 102, 4))
        self.min_c_label = pyglet.text.Label(
            str(self.this_player.min_c), x=SCREEN_W - 180,
            y=SCREEN_H - 20, anchor_x='center', anchor_y='center')
        self.mineral_small = UI(self, res.mineral_small, x=SCREEN_W - 210,
            y=SCREEN_H - 20)
        self.selected_icon = UI(self, res.none_img, CB_COORDS[0][0],
                                SCREEN_H - 72)
        self.selected_hp = pyglet.text.Label('', x=CB_COORDS[1][0] - 15,
                                             y=SCREEN_H - 72, anchor_y='center',
                                             font_size=8,
                                             color=(0, 0, 0,255))
        self.txt_out = pyglet.text.Label('', x=SCREEN_W / 2 - 50, y=100,
                anchor_x='center', anchor_y='center', font_size=8)
        self.txt_out_upd_f = None
        self.prod_bar_bg = UI(self, res.prod_bar_bg_img, CP_CENTER_X,
                              SCREEN_H - 93)
        self.prod_bar_bg.visible = False
        self.prod_bar = UI(self, res.prod_bar_img, SCREEN_W - 120, SCREEN_H - 94)
        self.prod_bar.visible = False
        self.prod_icon1 = UI(self, res.none_img, CB_COORDS[0][0], SCREEN_H - 110)
        self.prod_icon2 = UI(self, res.none_img, CB_COORDS[1][0], SCREEN_H - 110)
        self.prod_icon3 = UI(self, res.none_img, CB_COORDS[2][0], SCREEN_H - 110)

        # Hints
        self.hint = UI(self, res.hint_defiler, 100, 100)

        # Menu
        self.resume_b = UI(self, res.resume_img, SCREEN_W / 2, 300,
                           batch=menu_b_batch)
        self.save_b = UI(self, res.save_img, SCREEN_W / 2, 280,
                         batch=menu_b_batch)
        self.load_b = UI(self, res.load_img, SCREEN_W / 2, 260,
                         batch=menu_b_batch)
        self.restart_b = UI(self, res.restart_img, SCREEN_W / 2, 240,
                            batch=menu_b_batch)
        self.options_b = UI(self, res.options_img, SCREEN_W / 2, 220,
                            batch=menu_b_batch)
        self.exit_b = UI(self, res.exit_img, SCREEN_W / 2, 200,
                         batch=menu_b_batch)
        self.fullscreen_img = UI(self, res.fullscreen_img, SCREEN_W / 2, 200,
                         batch=options_batch)
        self.fullscreen_c = CheckB(self, SCREEN_W / 2 + 70, 200, False)
        self.back_b = UI(self, res.back_img, SCREEN_W / 2, 180,
                         batch=options_batch)

        # Control panel buttons
        self.armory_icon = UI(self, res.armory_icon_img, CB_COORDS[3][0],
                              CB_COORDS[3][1])
        self.turret_icon = UI(self, res.turret_icon_img, CB_COORDS[4][0],
                              CB_COORDS[4][1])
        self.mech_center_icon = UI(self, res.mech_center_icon_img,
                                   CB_COORDS[5][0], CB_COORDS[5][1])
        self.move_b = UI(self, res.move_img, CB_COORDS[0][0],
                         CB_COORDS[0][1])
        self.stop_b = UI(self, res.stop_img, CB_COORDS[1][0],
                         CB_COORDS[1][1])
        self.attack_b = UI(self, res.attack_img, CB_COORDS[2][0],
                           CB_COORDS[2][1])
        self.cancel_b = UI(self, res.cancel_img, CB_COORDS[8][0],
                           CB_COORDS[8][1])
        self.defiler_b = UI(self, res.defiler_img, CB_COORDS[0][0],
                            CB_COORDS[0][1])
        self.centurion_b = UI(self, res.centurion_img,
                              CB_COORDS[1][0], CB_COORDS[1][1])
        self.wyrm_b = UI(self, res.wyrm_img, CB_COORDS[2][0],
                         CB_COORDS[2][1])
        self.apocalypse_b = UI(self, res.apocalypse_img,
                               CB_COORDS[3][0], CB_COORDS[3][1])
        self.pioneer_b = UI(self, res.pioneer_img, CB_COORDS[4][0],
                            CB_COORDS[4][1])

        # Spawn buildings and minerals
        Mineral(self, PS / 2 + PS * 4, PS / 2 + PS * 7)
        Mineral(self, PS / 2 + PS * 4,  PS / 2 + PS * 8)
        Mineral(self, PS / 2 + PS * 6, PS / 2 + PS * 4)
        Mineral(self, PS / 2 + PS * 7, PS / 2 + PS * 3)
        Mineral(self, PS / 2 + PS * 10, PS / 2 + PS * 4)
        Mineral(self, PS / 2 + PS * 11, PS / 2 + PS * 4)

        Mineral(self, PS / 2 + PS * 52, PS / 2 + PS * 47)
        Mineral(self, PS / 2 + PS * 52, PS / 2 + PS * 46)
        Mineral(self, PS / 2 + PS * 46, PS / 2 + PS * 46)
        Mineral(self, PS / 2 + PS * 46, PS / 2 + PS * 48)
        self.our_1st_base = MechCenter(self, PS * 7, PS * 8, skip_constr=True)
        selected = self.our_1st_base
        self.selected_icon.image = selected.icon
        MechCenter(self, PS * 10, PS * 10, owner=self.computer, skip_constr=True)
        MechCenter(self, PS * 50, PS * 50, owner=self.computer, skip_constr=True)

        self.sel_spt = Sprite(img=res.sel_img, x=self.our_1st_base.x,
                              y=self.our_1st_base.y)
        self.sel_big_spt = Sprite(img=res.sel_big_img, x=self.our_1st_base.x,
                                  y=self.our_1st_base.y)
        self.rp_spt = Sprite(img=res.rp_img, x=self.our_1st_base.rp_x,
                             y=self.our_1st_base.rp_y)

        self.basic_unit_c_bs = [self.move_b, self.stop_b, self.attack_b]
        self.cbs_2_render = self.our_1st_base.cbs
        self.to_build_spt = Sprite(img=res.armory_img, x=-100, y=-100)
        self.to_build_spt.color = (0, 255, 0)

        # Spawn units. Have to spawn them right here. I don't remember why.
        Pioneer(self, PS / 2 + PS * 8, PS / 2 + PS * 6).spawn()

    def on_draw(self):
        """
        Render the screen.
        """
        # Initialize Projection matrix
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        # Initialize Modelview matrix
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # Save the default modelview matrix
        glPushMatrix()

        # Clear window with ClearColor
        glClear(GL_COLOR_BUFFER_BIT)

        # Me playing with OpenGL
        # glViewport(0, 0, SCREEN_WIDTH - 179, SCREEN_HEIGHT)

        # Set orthographic projection matrix
        glOrtho(lvb, lvb + SCREEN_W, bvb, bvb + SCREEN_H, 1, -1)

        if not self.paused:
            self.terrain.draw()
            ground_shadows_batch.draw()
            structures_batch.draw()
            ground_units_batch.draw()
            ground_team_color_batch.draw()
            weapons_batch.draw()
            explosions_batch.draw()
            air_shadows_batch.draw()
            air_batch.draw()
            air_team_color_batch.draw()
            if selected:
                try:
                    selected.is_big
                    self.sel_big_spt.draw()
                except AttributeError:
                    self.sel_spt.draw()

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            self.fow_texture = self.mm_fow_img.get_texture()
            self.fow_texture.width = 3264
            self.fow_texture.height = 3264
            self.fow_texture.blit(-32, -32)
            utilities_batch.draw()
            if self.build_loc_sel_phase:
                self.to_build_spt.draw()
            self.cp_spt.draw()
            self.menu_b.draw()
            self.sel_frame_cp.draw()
            self.selected_icon.draw()
            self.prod_bar_bg.draw()
            self.prod_bar.draw()
            self.prod_icon1.draw()
            self.prod_icon2.draw()
            self.prod_icon3.draw()
            self.selected_hp.draw()
            self.cp_b_bg.draw()
            self.mm_textured_bg.draw()
            minimap_pixels_batch.draw()

            if self.cbs_2_render:
                for button in self.cbs_2_render:
                    button.draw()
                if selected in our_structs and selected \
                        not in offensive_structs:
                    self.rp_spt.draw()

            self.fow_texture.width = 102
            self.fow_texture.height = 102
            self.fow_texture.blit(minimap_fow_x, minimap_fow_y)

            self.mm_cam_frame_spt.draw()
            self.min_c_label.draw()
            self.mineral_small.draw()
            if self.show_fps:
                self.fps_display.draw()

            if self.show_hint:
                self.hint.draw()
            self.txt_out.draw()
        else:
            self.menu_bg.draw()
            if self.options:
                options_batch.draw()
                check_batch.draw()
            else:
                menu_b_batch.draw()

        # Remove default modelview matrix
        glPopMatrix()

    def update(self, delta_time):
        global selected
        if not self.paused:
            self.f += 1
            # Build units
            for struct in prod_structs:
                try:
                    building_spawn_unit(self, struct)
                    if not struct.prod_q:
                        struct.prod_complete = True
                except AttributeError:
                    pass
            # AI
            if self.f % 50 == 0:
                self.ai()
            # Units
            # Gathering resources
            for worker in workers:
                if worker.mineral_to_gather and worker.dest_reached:
                    if not worker.is_gathering:
                        try:
                            if is_melee_dist(worker, worker.task_x,
                                             worker.task_y):
                                # print("melee dist")
                                worker.gather()
                        except TypeError:
                            worker.clear_task()
                    else:
                        worker.mineral_to_gather.hp -= 0.03
                        owner = worker.owner
                        owner.min_c += 0.03
                        if owner.name == 'player1':
                            self.update_min_c_label()
            # Summon structures
            for worker in workers:
                if worker.to_build:
                    if worker.to_build == 'mech_center':
                        if is_2_melee_dist(worker, worker.task_x,
                                           worker.task_y):
                            worker.build()
                    else:
                        if is_melee_dist(worker, worker.task_x, worker.task_y):
                            worker.build()
            # Finish summoning Guardian structures
            if self.f % 10 == 0:
                for struct in guardian_dummies:
                    try:
                        if struct.const_f + struct.build_time <= \
                                self.f:
                            struct.constr_complete()
                            delayed_del = (struct, guardian_dummies)
                    except AttributeError:
                        pass
                # Delayed del
                try:
                    del delayed_del[1][delayed_del[1].index(
                        delayed_del[0])]
                except:
                    pass
            # Movement
            for unit in our_units + enemy_units:
                if not unit.dest_reached:
                    # Do not jump
                    if not unit.eta() <= 1:
                        unit.update()
                        if selected == unit:
                            self.sel_spt.x = unit.x
                            self.sel_spt.y = unit.y
                    # Jump
                    else:
                        if not unit.move_interd:
                            unit.x = unit.target_x
                            unit.y = unit.target_y
                            unit.team_color.x = unit.target_x
                            unit.team_color.y = unit.target_y
                            if selected == unit:
                                self.sel_spt.x = unit.x
                                self.sel_spt.y = unit.y
                            if not unit.flying:
                                unit.shadow.x = unit.target_x + 3
                                unit.shadow.y = unit.target_y - 3
                            else:
                                unit.shadow.x = unit.target_x + 10
                                unit.shadow.y = unit.target_y - 10
                            unit.pos_dict[
                                (unit.target_x, unit.target_y)] = unit
                            if unit.x == unit.dest_x and unit.y == \
                                    unit.dest_y:
                                unit.dest_reached = True
                            else:
                                if unit.attack_moving:
                                    if unit.owner.name == 'player1':
                                        if closest_enemy_2_att(unit,
                                                enemy_units + enemy_structs):
                                            unit.dest_reached = True
                                            unit.attack_moving = False
                                        else:
                                            unit.update_move()
                                    else:
                                        if closest_enemy_2_att(unit,
                                                our_units + our_structs):
                                            unit.dest_reached = True
                                            unit.attack_moving = False
                                        else:
                                            unit.update_move()
                                else:
                                    unit.update_move()
                        # Movement interrupted
                        else:
                            unit.x = unit.target_x
                            unit.y = unit.target_y
                            unit.team_color.x = unit.target_x
                            unit.team_color.y = unit.target_y
                            if not unit.flying:
                                unit.shadow.x = unit.target_x + 3
                                unit.shadow.y = unit.target_y - 3
                                g_pos_coord_d[(unit.target_x, unit.target_y)] \
                                    = unit
                            else:
                                unit.shadow.x = unit.target_x + 10
                                unit.shadow.y = unit.target_y - 10
                                a_pos_coord_d[(unit.target_x, unit.target_y)] \
                                    = unit
                            unit.dest_reached = True
                            unit.move((unit.new_dest_x, unit.new_dest_y))
                            unit.move_interd = False
                        if unit in our_units:
                            self.update_fow(unit.x, unit.y, unit.vision_radius)
                else:
                    try:
                        unit.to_build = None
                        unit.task_x = None
                        unit.task_y = None
                    except AttributeError:
                        pass
            # Shooting
            update_shooting(self, offensive_structs + our_units,
                            enemy_structs + enemy_units)
            update_shooting(self, enemy_units, our_structs + our_units)
            # Projectiles
            delayed_del = []
            for i, projectile in enumerate(projectiles):
                if not projectile.eta() <= 1:
                    projectile.update()
                else:  # Hit!
                    projectile.target_obj.hp -= projectile.damage
                    HitAnim(projectile.x, projectile.y)
                    delayed_del.append(projectile)
            for projectile in delayed_del:
                projectiles.remove(projectile)
                projectile.delete()
            # Zaps
            delayed_del = []
            for zap in zaps:
                if zap.f_started + ZAPS_LAST_F <= self.f:
                    delayed_del.append(zap)
            for zap in delayed_del:
                zaps.remove(zap)
                zap.delete()
            # Bombs
            delayed_del = []
            for i, bomb in enumerate(bombs):
                if not bomb.eta() <= 1:
                    bomb.update()
                else:  # Hit!
                    try:
                        g_pos_coord_d[(bomb.target_x, bomb.target_y)].hp -= \
                            bomb.damage
                    # This is because of 2-block-wide
                    # structures and the way enemy-finding workds
                    except KeyError:
                        try:
                            g_pos_coord_d[(bomb.target_x - 16,
                                           bomb.target_y - 16)].hp -= bomb.damage
                        except AttributeError:
                            pass
                    except AttributeError:  # For already dead? Errr
                        pass
                    hit_anim = HitAnim(bomb.x, bomb.y)
                    hit_anim.color = (255, 200, 200)
                    delayed_del.append(bomb)
            for bomb in delayed_del:
                bombs.remove(bomb)
                bomb.delete()
            # Destroying minerals
            minerals_to_del = []
            for mineral in minerals:
                if mineral.hp <= 0:
                    mineral.kill()
                    minerals_to_del.append(mineral)
            for mineral in minerals_to_del:
                minerals.remove(mineral)
            # Destroying targets
            for entity in our_structs + our_units + \
                          enemy_structs + enemy_units:
                if entity.hp <= 0:
                    if entity.owner.name == 'computer1' and \
                            isinstance(entity, Pioneer):
                        self.computer.workers_count -= 1
                    entity.kill()
                    if entity == selected:
                        selected = None
            if self.f % 10 == 0:
                # Update hp label
                try:
                    selected.max_hp
                    self.selected_hp.text = str(int(selected.hp)) + '/' + \
                                            str(selected.max_hp)
                except AttributeError:
                    try:
                        self.selected_hp.text = str(int(selected.hp))
                    except AttributeError:  # The entity is no more
                        self.selected_icon.image = res.none_img
                        self.selected_hp.text = ''
                # Reset txt_out
                if self.txt_out_upd_f:
                    if self.f >= self.txt_out_upd_f + TXT_OUT_DECAY:
                        self.txt_out.text = ''
                        self.txt_out_upd_f = None
                # Production bar
                try:
                    if not selected.prod_complete:
                        self.prod_bar.scale_x = (self.f - selected.prod_start_f) \
                        * 100 / selected.cur_max_prod_time + 1
                    else:
                        self.prod_bar_bg.visible = False
                        self.prod_bar.visible = False
                except (AttributeError, TypeError):
                    pass
        if self.f % 50 == 0:
            if not enemy_structs:
                self.txt_out.text = "Victory"
                self.txt_out_upd_f = self.f
            elif not our_structs:
                self.txt_out.text = "Defeat"
                self.txt_out_upd_f = self.f

    def on_key_press(self, symbol, modifiers):
        """Called whenever a key is pressed."""
        global selected, lvb, bvb
        if symbol == key.F:
            if self.fullscreen:
                self.set_fullscreen(False)
            else:
                self.set_fullscreen(True)
        if not self.paused:
            if symbol == key.F1:
                if not self.show_fps:
                    self.show_fps = True
                else:
                    self.show_fps = False
            elif symbol == key.F2:
                self.save()
            elif symbol == key.F3:
                self.load()
            elif symbol == key.F4:
                # Removes FOW
                self.npa[:, :, 3] = 0
                self.mm_fow_ImageData.set_data('RGBA',
                    self.mm_fow_ImageData.width * 4, data=self.npa.tobytes())
            elif symbol == key.F5:
                self.this_player.min_c = 99999
                self.update_min_c_label()
            elif symbol == key.F6:
                self.this_player.min_c = 0
                self.update_min_c_label()
            elif symbol == key.DELETE:
                # Kill entity
                if selected in our_units:
                    selected.kill()
                    if selected.flying:
                        a_pos_coord_d[(self.sel_spt.x, self.sel_spt.y)] = None
                    else:
                        g_pos_coord_d[(self.sel_spt.x, self.sel_spt.y)] = None
                    selected = None
                elif selected in our_structs:
                    selected.kill()
                    selected = None
            elif symbol == key.ESCAPE:
                # Cancel command
                self.build_loc_sel_phase = False
                self.targeting_phase = False
                self.m_targeting_phase = False
                self.set_mouse_cursor(res.cursor)
            elif symbol == key.LEFT:
                lvb -= PS
                self.update_viewport()
            elif symbol == key.RIGHT:
                lvb += PS
                self.update_viewport()
            elif symbol == key.DOWN:
                bvb -= PS
                self.update_viewport()
            elif symbol == key.UP:
                bvb += PS
                self.update_viewport()
            elif symbol == key.Q:
                # Move
                if selected in our_units and selected.owner.name == "player1":
                    self.set_mouse_cursor(res.cursor_target)
                    self.m_targeting_phase = True
                    return
                # Build defiler
                elif isinstance(selected, MechCenter):
                    order_unit(self, selected, Defiler)
            elif symbol == key.W:
                # Stop
                if selected in our_units:
                    try:
                        selected.stop_move()
                    except AttributeError:
                        pass
                # Build centurion
                elif isinstance(selected, MechCenter):
                    order_unit(self, selected, Centurion)
            elif symbol == key.E:
                # Attack move
                if selected in our_units:
                    try:
                        if selected.weapon_type != 'none':
                            if selected.owner.name == 'player1':
                                self.set_mouse_cursor(res.cursor_target)
                            self.targeting_phase = True
                    except AttributeError:
                        pass
                # Build wyrm
                elif isinstance(selected, MechCenter):
                    order_unit(self, selected, Wyrm)
            elif symbol == key.A:
                # Build armory
                if str(type(selected)) == "<class '__main__.Pioneer'>":
                    self.to_build_spt.image = res.armory_img
                    self.to_build = "armory"
                    self.hotkey_constr_cur_1b()
                # Build apocalypse
                elif isinstance(selected, MechCenter):
                    order_unit(self, selected, Apocalypse)
            elif symbol == key.S:
                # Build turret
                if str(type(selected)) == "<class '__main__.Pioneer'>":
                    self.to_build_spt.image = res.turret_icon_img
                    self.to_build = "turret"
                    self.hotkey_constr_cur_1b()
                # Build pioneer
                elif isinstance(selected, MechCenter):
                    order_unit(self, selected, Pioneer)
            elif symbol == key.D:
                # Build mech center
                if str(type(selected)) == "<class '__main__.Pioneer'>":
                    self.to_build_spt.image = res.mech_center_img
                    self.build_loc_sel_phase = True
                    self.to_build = "mech_center"
                    x, y = win32api.GetCursorPos()
                    x, y = x / 2, y / 2
                    y = SCREEN_H - y
                    x, y = mc(x=x, y=y)
                    x, y = round_coords(x, y)
                    s_x = int((x - 16) / 32) + 1
                    s_y = int((y - 16) / 32) + 1
                    s_coords_to_check = [(s_x, s_y), (s_x + 1, s_y),
                                         (s_x + 1, s_y + 1), (s_x, s_y + 1)]
                    no_place = False
                    for c in s_coords_to_check:
                        if self.npa[c[1], c[0], 3] != 0:
                            no_place = True
                            break
                    if no_place is False:
                        coords_to_check = [(x, y), (x + PS, y),
                                           (x + PS, y + PS), (x, y + PS)]
                        for c in coords_to_check:
                            if g_pos_coord_d[c[0], c[1]]:
                                no_place = True
                                break
                    if no_place:
                        self.to_build_spt.color = (255, 0, 0)
                        self.loc_clear = False
                    else:
                        self.loc_clear = True
                        self.to_build_spt.color = (0, 255, 0)
                    x += PS / 2
                    y += PS / 2
                    self.to_build_spt.x, self.to_build_spt.y = x, y
            elif symbol == key.C:
                self.cancel_prod()
            elif symbol == key.X:
                # Deletes all our units on the screen
                coords_to_delete = []
                yi = bvb + PS // 2
                for y in range(yi, yi + 12 * PS, PS):
                    xi = lvb + PS // 2
                    for x in range(xi, xi + 17 * PS, PS):
                        coords_to_delete.append((x, y))
                for coord in coords_to_delete:
                    for unit in our_units:
                        if g_pos_coord_d[coord[0], coord[1]] == unit:
                            unit.kill()
            elif symbol == key.Z:
                # Fills the entire map with wyrms
                i = 0
                for _key, value in g_pos_coord_d.items():
                    if i % 1 == 0:
                        if value is None:
                            unit = Wyrm(self, _key[0], _key[1])
                            unit.spawn()
                    i += 1
            elif symbol == key.V:
                pass
                # print(lvb, bvb)
                # print(lvb % 32 == 0, bvb % 32 == 0)
        # Menu
        else:
            if symbol == key.ESCAPE:
                self.paused = False

    def on_mouse_press(self, x, y, button, modifiers):
        """Don't play with mc(), globals"""
        global selected, lvb, bvb
        if self.fullscreen:
            x //= 2
            y //= 2
        if not self.paused:
            # Building location selection
            if self.build_loc_sel_phase:
                # Game field
                if x < SCREEN_W - 139:
                    x, y = round_coords(x, y)
                    if button == mouse.LEFT:
                        if self.loc_clear:
                            if self.to_build == 'armory':
                                building = Armory
                            elif self.to_build == 'turret':
                                building = Turret
                            else:
                                building = MechCenter
                            order_structure(self, selected, building, x, y)
                            self.build_loc_sel_phase = False
                    elif button == mouse.RIGHT:
                        self.build_loc_sel_phase = False
            # Movement target selection phase
            elif self.m_targeting_phase:
                x, y = mc(x=x, y=y)
                # Game field
                if x < SCREEN_W - 139:
                    pass
                # Minimap
                elif MM0X <= x <= MM0X + 100 and MM0Y <= y <= MM0Y + 100:
                    x = (x - MM0X) * PS
                    y = (y - MM0Y) * PS
                else:
                    return
                x, y = round_coords(x, y)
                if selected.dest_reached:
                    selected.move((x, y))
                # Movement interruption
                else:
                    selected.move_interd = True
                    selected.new_dest_x = x
                    selected.new_dest_y = y
                selected.has_target_p = False
                self.m_targeting_phase = False
                self.set_mouse_cursor(res.cursor)
            # Targeting phase
            elif self.targeting_phase:
                if button == mouse.LEFT:
                    x, y = mc(x=x, y=y)
                    # Game field
                    if x < SCREEN_W - 139:
                        pass
                    # Minimap
                    elif MM0X <= x <= MM0X + 100 and MM0Y <= y <= MM0Y + 100:
                        x = (x - MM0X) * PS
                        y = (y - MM0Y) * PS
                    else:
                        return
                    x, y = round_coords(x, y)
                    selected.attack_moving = True
                    selected.move((x, y))
                    self.targeting_phase = False
                    self.set_mouse_cursor(res.cursor)
            # Normal phase
            else:
                self.show_hint = False  # Fixes a bug with hints
                # Game field
                if x < SCREEN_W - 139:
                    x, y = round_coords(x, y)
                    x, y = mc(x=x, y=y)
                    if button == mouse.LEFT:
                        # Selection
                        if not bin(modifiers)[-1] == '1':  # Shift is pressed
                            to_be_selected = a_pos_coord_d[(x, y)]
                            if to_be_selected:  # Air unit found
                                selected = to_be_selected
                                self.sel_spt.x = x
                                self.sel_spt.y = y
                            else:
                                to_be_selected = g_pos_coord_d[(x, y)]
                                if to_be_selected:
                                    try:
                                        to_be_selected.is_big
                                        self.sel_big_spt.x = to_be_selected.x
                                        self.sel_big_spt.y = to_be_selected.y
                                    except AttributeError:
                                        self.sel_spt.x = x
                                        self.sel_spt.y = y
                                    selected = to_be_selected
                        else:
                            to_be_selected = g_pos_coord_d[(x, y)]
                            if to_be_selected:
                                try:
                                    to_be_selected.is_big
                                    self.sel_big_spt.x = to_be_selected.x
                                    self.sel_big_spt.y = to_be_selected.y
                                except AttributeError:
                                    self.sel_spt.x = x
                                    self.sel_spt.y = y
                                selected = to_be_selected
                        self.selected_icon.image = selected.icon
                        try:
                            self.selected_hp.text = str(int(selected.hp)) \
                                + '/' + str(selected.max_hp)
                        except AttributeError:
                            self.selected_hp.text = str(int(selected.hp))
                        # Production
                        if selected.owner.name == 'player1':
                            try:
                                selected.prod_q[0]
                                self.prod_bar_bg.visible = True
                                self.prod_bar.visible = True
                                self.prod_icon1.visible = True
                                self.prod_icon2.visible = True
                                self.prod_icon3.visible = True
                            # Not a structure or nothing in production
                            except (AttributeError, IndexError):
                                self.prod_bar_bg.visible = False
                                self.prod_bar.visible = False
                                self.prod_icon1.visible = False
                                self.prod_icon2.visible = False
                                self.prod_icon3.visible = False
                        # Control buttons
                        try:
                            if selected.owner.name == 'player1':
                                try:
                                    if not selected.under_constr:
                                        self.cbs_2_render = selected.cbs
                                    else:
                                        self.cbs_2_render = None
                                except AttributeError:
                                    self.cbs_2_render = selected.cbs
                            else:
                                self.cbs_2_render = None
                        except AttributeError:  # For minerals
                            self.cbs_2_render = None
                        try:
                            self.rp_spt.x = selected.rp_x
                            self.rp_spt.y = selected.rp_y
                        except AttributeError:
                            pass
                    elif button == mouse.RIGHT:
                        # Rally point
                        if selected in our_structs:
                            if g_pos_coord_d[x, y] != selected:
                                selected.rp_x = x
                                selected.rp_y = y
                                selected.default_rp = False
                                self.rp_spt.x = x
                                self.rp_spt.y = y
                            else:
                                selected.default_rp = True
                                self.rp_spt.x = selected.x
                                self.rp_spt.y = selected.y
                            # print('Rally set to ({}, {})'.format(x, y))
                        # A unit is selected
                        else:
                            if selected in our_units:
                                if selected.dest_reached:
                                    selected.move((x, y))
                                # Movement interruption
                                else:
                                    selected.move_interd = True
                                    selected.new_dest_x = x
                                    selected.new_dest_y = y
                                selected.has_target_p = False
                                # Gathering
                                if selected.path:
                                    if str(type(selected)) == \
                                            "<class '__main__.Pioneer'>":
                                        selected.clear_task()
                                        obj = g_pos_coord_d[(x, y)]
                                        if str(type(obj)) == \
                                                "<class '__main__.Mineral'>":
                                            # print('go gather, lazy worker!')
                                            selected.mineral_to_gather = obj
                                            selected.task_x = obj.x
                                            selected.task_y = obj.y
                                            obj.workers.append(selected)
                # Minimap
                elif MM0X <= x <= MM0X + 100 and MM0Y <= y <= MM0Y + 100:
                    if button == mouse.LEFT:
                        # The viewport is 17x12 blocks. This +2 is
                        # about 2 border pixels of the frame
                        x -= 19 // 2
                        y -= 14 // 2
                        # print('x =', x, 'y =', y)
                        lvb = (x - MM0X) * PS
                        bvb = (y - MM0Y) * PS
                        self.update_viewport()
                    elif button == mouse.RIGHT:
                        x = (x - MM0X) * PS
                        y = (y - MM0Y) * PS
                        x, y = round_coords(x, y)
                        # A unit is selected
                        unit_found = False
                        for unit in our_units:
                            if unit == selected:
                                unit_found = True
                                if unit.dest_reached:
                                    unit.move((x, y))
                                else:  # Movement interruption
                                    unit.dest_x = unit.target_x
                                    unit.dest_y = unit.target_y
                                    unit.move_interd = True
                                    unit.new_dest_x = x
                                    unit.new_dest_y = y
                        if not unit_found:
                            if selected in our_structs:
                                selected.rp_x = x
                                selected.rp_y = y
                                self.rp_spt.x = x
                                self.rp_spt.y = y
                                # print('Rally set to ({}, {})'.format(x, y))
                # Control panel other
                else:
                    x, y = mc(x=x, y=y)
                    w = self.menu_b.width
                    h = self.menu_b.height
                    if self.menu_b.x - w // 2 <= x <= \
                            self.menu_b.x + w // 2 and \
                            self.menu_b.y - h // 2 <= y <= \
                            self.menu_b.y + h // 2:
                        self.paused = True
                        return
                    # Build units
                    if selected in our_structs and not selected.under_constr:
                        # Create defiler
                        if self.defiler_b.x - 16 <= x <= \
                                self.defiler_b.x + 16 and \
                                self.defiler_b.y - 16 <= y <= \
                                self.defiler_b.y + 16:
                            order_unit(self, selected, Defiler)
                        # Create centurion
                        elif self.centurion_b.x - 16 <= x <= \
                                self.centurion_b.x + 16 and \
                                self.centurion_b.y - 16 <= y <= \
                                self.centurion_b.y + 16:
                            order_unit(self, selected, Centurion)
                        # Create wyrm
                        elif self.wyrm_b.x - 16 <= x <= \
                                self.wyrm_b.x + 16 and \
                                self.wyrm_b.y - 16 <= y <= \
                                self.wyrm_b.y + 16:
                            order_unit(self, selected, Wyrm)
                        # Create apocalypse
                        elif self.apocalypse_b.x - 16 <= x <= \
                                self.apocalypse_b.x + 16 and \
                                self.apocalypse_b.y - 16 <= y <= \
                                self.apocalypse_b.y + 16:
                            order_unit(self, selected, Apocalypse)
                        # Create pioneer
                        elif self.pioneer_b.x - 16 <= x <= \
                                self.pioneer_b.x + 16 and \
                                self.pioneer_b.y - 16 <= y <= \
                                self.pioneer_b.y + 16:
                            order_unit(self, selected, Pioneer)
                        # Cancel last order
                        elif self.cancel_b.x - 16 <= x <= \
                                self.cancel_b.x + 16 and \
                                self.cancel_b.y - 16 <= y <= \
                                self.cancel_b.y + 16:
                            self.cancel_prod()
                    elif selected in our_units:
                        # Move
                        if self.move_b.x - 16 <= x <= self.move_b.x + 16 and \
                                self.move_b.y - 16 <= y <= self.move_b.y + 16:
                            self.set_mouse_cursor(res.cursor_target)
                            self.m_targeting_phase = True
                            return
                        # Stop
                        if self.stop_b.x - 16 <= x <= self.stop_b.x + 16 and \
                                self.stop_b.y - 16 <= y <= self.stop_b.y + 16:
                            selected.stop_move()
                            return
                        # Attack
                        if self.attack_b.x - 16 <= x <= self.attack_b.x + 16 \
                                and self.attack_b.y - 16 <= y <= \
                                self.attack_b.y + 16:
                            try:
                                if selected.weapon_type != 'none':
                                    if selected.owner.name == 'player1':
                                        self.set_mouse_cursor(
                                            res.cursor_target)
                                    self.targeting_phase = True
                            except AttributeError:
                                pass
                            return
                        # Construct structures
                        if str(type(selected)) == "<class '__main__.Pioneer'>":
                            if self.armory_icon.x - 16 <= x <= \
                                    self.armory_icon.x + 16 and \
                                    self.armory_icon.y - 16 <= y <= \
                                    self.armory_icon.y + 16:
                                self.to_build_spt.image = res.armory_img
                                self.to_build_spt.color = (0, 255, 0)
                                self.build_loc_sel_phase = True
                                self.to_build = "armory"
                                self.to_build_spt.x, self.to_build_spt.y = x, y
                            elif self.turret_icon.x - 16 <= x <= \
                                    self.turret_icon.x + 16 and \
                                    self.turret_icon.y - 16 <= y <= \
                                    self.turret_icon.y + 16:
                                self.to_build_spt.image = res.turret_icon_img
                                self.to_build_spt.color = (0, 255, 0)
                                self.build_loc_sel_phase = True
                                self.to_build = "turret"
                                self.to_build_spt.x, self.to_build_spt.y = x, y
                            elif self.mech_center_icon.x - 16 <= x <= \
                                    self.mech_center_icon.x + 16 and \
                                    self.mech_center_icon.y - 16 <= y <= \
                                    self.mech_center_icon.y + 16:
                                self.to_build_spt.image = res.mech_center_img
                                self.to_build_spt.color = (0, 255, 0)
                                self.build_loc_sel_phase = True
                                self.to_build = "mech_center"
                                self.to_build_spt.x, self.to_build_spt.y = x, y
        # Paused
        else:
            x, y = mc(x=x, y=y)
            if self.options:
                if self.fullscreen_c.x - 8 <= x <= self.fullscreen_c.x + 8 \
                    and \
                   self.fullscreen_c.y - 8 <= y <= self.fullscreen_c.y + 8:
                    if self.fullscreen:
                        self.set_fullscreen(False)
                        self.fullscreen_c.check.visible = False
                    else:
                        self.set_fullscreen(True)
                        self.fullscreen_c.check.visible = True
                elif self.back_b.x - 25.5 <= x <= self.back_b.x + 25.5 and \
                        self.back_b.y - 8 <= y <= self.back_b.y + 8:
                    self.options = False
            else:
                if self.resume_b.x - 48 <= x <= self.resume_b.x + 48 and \
                   self.resume_b.y - 8 <= y <= self.resume_b.y + 8:
                    self.paused = False
                elif self.options_b.x - 48 <= x <= self.options_b.x + 48 and \
                     self.options_b.y - 8 <= y <= self.options_b.y + 8:
                    self.options = True
                elif self.exit_b.x - 48 <= x <= self.exit_b.x + 48 and \
                     self.exit_b.y - 8 <= y <= self.exit_b.y + 8:
                    sys.exit()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.fullscreen:
            x /= 2
            y /= 2
        if not self.paused and self.build_loc_sel_phase:
            self.mouse_x = x
            self.mouse_y = y
            if self.to_build == "mech_center":
                x, y = round_coords(x, y)
                self.to_build_spt.x = x + lvb + PS / 2
                self.to_build_spt.y = y + bvb + PS / 2
                x, y = mc(x=x, y=y)
                s_x = int((x - 16) / 32) + 1
                s_y = int((y - 16) / 32) + 1
                s_coords_to_check = [(s_x, s_y), (s_x + 1, s_y),
                                     (s_x + 1, s_y + 1), (s_x, s_y + 1)]
                no_place = False
                for c in s_coords_to_check:
                    if self.npa[c[1], c[0], 3] != 0:
                        no_place = True
                        break
                if no_place is False:
                    coords_to_check = [(x, y), (x + PS, y),
                                       (x + PS, y + PS), (x, y + PS)]
                    for c in coords_to_check:
                        if g_pos_coord_d[c[0], c[1]]:
                            no_place = True
                            break
                if no_place:
                    self.to_build_spt.color = (255, 0, 0)
                    self.loc_clear = False
                else:
                    self.loc_clear = True
                    self.to_build_spt.color = (0, 255, 0)
            # Other buildings
            else:
                x, y = round_coords(x, y)
                self.to_build_spt.x = x + lvb
                self.to_build_spt.y = y + bvb
                x, y = mc(x=x, y=y)
                x = int((x - 16) / 32) + 1
                y = int((y - 16) / 32) + 1
                if g_pos_coord_d[self.to_build_spt.x, self.to_build_spt.y] or \
                        self.npa[y, x, 3] != 0:
                    self.to_build_spt.color = (255, 0, 0)
                    self.loc_clear = False
                else:
                    self.to_build_spt.color = (0, 255, 0)
                    self.loc_clear = True
        elif not self.paused:
            # Hits
            if isinstance(selected, MechCenter):
                # Defiler
                if CB_COORDS[0][0] - 16 <= x <= CB_COORDS[0][0] + \
                        16 and CB_COORDS[0][1] - 16 <= y <= \
                        CB_COORDS[0][1] + 16:
                    self.hint.image = res.hint_defiler
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                # Centurion
                elif CB_COORDS[1][0] - 16 <= x <= CB_COORDS[1][0] + \
                        16 and CB_COORDS[1][1] - 16 <= y <= \
                        CB_COORDS[1][1] + 16:
                    self.hint.image = res.hint_centurion
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                # Wyrm
                elif CB_COORDS[2][0] - 16 <= x <= CB_COORDS[2][0] + \
                        16 and CB_COORDS[2][1] - 16 <= y <= \
                        CB_COORDS[2][1] + 16:
                    self.hint.image = res.hint_wyrm
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                # Apocalypse
                elif CB_COORDS[3][0] - 16 <= x <= CB_COORDS[3][0] + \
                        16 and CB_COORDS[3][1] - 16 <= y <= \
                        CB_COORDS[3][1] + 16:
                    self.hint.image = res.hint_apocalypse
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                # Pioneer
                elif CB_COORDS[4][0] - 16 <= x <= CB_COORDS[4][0] + \
                        16 and CB_COORDS[4][1] - 16 <= y <= \
                        CB_COORDS[4][1] + 16:
                    self.hint.image = res.hint_pioneer
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                else:
                    self.show_hint = False
            elif isinstance(selected, Pioneer):
                # Armory
                if CB_COORDS[3][0] - 16 <= x <= CB_COORDS[3][0] + \
                        16 and CB_COORDS[3][1] - 16 <= y <= \
                        CB_COORDS[3][1] + 16:
                    self.hint.image = res.hint_armory
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                    # Armory
                elif CB_COORDS[4][0] - 16 <= x <= CB_COORDS[4][0] + \
                        16 and CB_COORDS[4][1] - 16 <= y <= \
                        CB_COORDS[4][1] + 16:
                    self.hint.image = res.hint_turret
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                elif CB_COORDS[5][0] - 16 <= x <= CB_COORDS[5][0] + \
                        16 and CB_COORDS[5][1] - 16 <= y <= \
                        CB_COORDS[5][1] + 16:
                    self.hint.image = res.hint_mech_center
                    self.hint.x = x + lvb
                    self.hint.y = y + bvb
                    self.show_hint = True
                else:
                    self.show_hint = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        global lvb, bvb
        if not self.paused:
            if self.fullscreen:
                x /= 2
                y /= 2
                dx /= 2
                dy /= 2
            if not self.minimap_drugging:
                # Game field
                if x < SCREEN_W - 139 and buttons == 2:
                    self.dx += dx * MMB_PAN_SPEED
                    self.dy += dy * MMB_PAN_SPEED
                    if abs(self.dx) >= PS:
                        if self.dx < 0:
                            lvb += PS
                            self.update_viewport()
                            self.dx -= self.dx
                        else:
                            lvb -= PS
                            self.update_viewport()
                            self.dx -= self.dx
                    if abs(self.dy) >= PS:
                        if self.dy < 0:
                            bvb += PS
                            self.update_viewport()
                            self.dy -= self.dy
                        else:
                            bvb -= PS
                            self.update_viewport()
                            self.dy -= self.dy
                # Minimap
                elif MM0X <= x <= MM0X + 100 and MM0Y <= y <= MM0Y + 100 \
                        and buttons in [1, 2]:
                    self.minimap_drugging = True
                    lvb += dx * PS
                    bvb += dy * PS
                    self.update_viewport()
            # Minimap dragging
            else:
                lvb += dx * PS
                bvb += dy * PS
                self.update_viewport()

    def on_mouse_release(self, x, y, button, modifiers):
        self.minimap_drugging = False

    def update_viewport(self):
        global lvb, bvb, minimap_fow_x, minimap_fow_y
        # Viewport limits
        cp_limit = POS_COORDS_N_COLUMNS * PS - SCREEN_W // PS * PS + PS * 4
        if lvb % PS != 0:
            lvb += PS // 2
        if bvb % PS != 0:
            bvb += PS // 2
        if lvb < 0:
            lvb = 0
        elif lvb > cp_limit:
            lvb = cp_limit
        if bvb < 0:
            bvb = 0
        elif bvb > POS_COORDS_N_ROWS * PS - SCREEN_H:
            bvb = POS_COORDS_N_ROWS * PS - SCREEN_H

        self.mm_textured_bg.x = MM0X + lvb
        self.mm_textured_bg.y = MM0Y + bvb
        for el in self.ui:
            el.x = el.org_x + lvb
            el.y = el.org_y + bvb
        self.min_c_label.x = SCREEN_W - 180 + lvb
        self.min_c_label.y = SCREEN_H - 20 + bvb
        self.selected_hp.x = CB_COORDS[1][0] - 15 + lvb
        self.selected_hp.y = SCREEN_H - 72 + bvb
        self.txt_out.x = SCREEN_W / 2 - 50 + lvb
        self.txt_out.y = 100 + bvb
        for entity in our_structs + our_units \
                      + enemy_structs + enemy_units:
            entity.pixel.x, entity.pixel.y = to_minimap(entity.x, entity.y)
        self.mm_cam_frame_spt.x, self.mm_cam_frame_spt.y = to_minimap(lvb, bvb)
        self.mm_cam_frame_spt.x -= 1
        self.mm_cam_frame_spt.y -= 1
        minimap_fow_x = MM0X - 1 + lvb
        minimap_fow_y = MM0Y - 1 + bvb

    def update_fow(self, x, y, radius):
        x = int((x - 16) / 32) + 1
        y = int((y - 16) / 32) + 1
        for yi in range(-radius + y, radius + 1 + y):
            if 0 <= yi <= 101:
                for xi in range(-radius + x, radius + 1 + x):
                    if 0 <= xi <= 101:
                        if ((xi - x) ** 2 + (yi - y) ** 2) ** 0.5 <= radius:
                            self.npa[yi, xi, 3] = 0
        self.mm_fow_ImageData.set_data('RGBA', self.mm_fow_ImageData.width
                                       * 4, data=self.npa.tobytes())

    def update_min_c_label(self):
        self.min_c_label.text = str(int(self.this_player.min_c))

    def hotkey_constr_cur_1b(self):
        self.build_loc_sel_phase = True
        x, y = win32api.GetCursorPos()
        x, y = x / 2, y / 2
        y = SCREEN_H - y
        x, y = mc(x=x, y=y)
        x, y = round_coords(x, y)
        self.to_build_spt.x, self.to_build_spt.y = x, y
        s_x = int((x - 16) / 32) + 1
        s_y = int((y - 16) / 32) + 1
        if g_pos_coord_d[self.to_build_spt.x, self.to_build_spt.y] \
                or self.npa[s_y, s_x, 3] != 0:
            self.to_build_spt.color = (255, 0, 0)
            self.loc_clear = False
        else:
            self.to_build_spt.color = (0, 255, 0)
            self.loc_clear = True

    def cancel_prod(self):
        try:
            self.this_player.min_c += selected.prod_q[-1].cost
            self.update_min_c_label()
            del selected.prod_q[-1]
            if not selected.prod_q:
                selected.anim.visible = False
                selected.prod_complete = True
            exec("self.prod_icon{}.image = res.none_img".format(
                len(selected.prod_q) + 1))
            self.prod_bar.scale_x = 1
        except (AttributeError, IndexError):
            return

    def ai(self):
        # AI ordering units
        for struct in enemy_structs:
            if isinstance(struct, MechCenter):
                if self.computer.workers_count < 6:
                    order_unit(self, struct, Pioneer)
                    self.computer.workers_count += 1
                else:
                    order_unit(self, struct, random.choice((Wyrm, Centurion,
                                                            Defiler, Apocalypse)))
        # AI gathering resources
        try:
            closest_min = minerals[0]
            for worker in workers:
                if all((not worker.is_gathering,
                        worker.dest_reached,
                        worker.owner.name == 'computer1')):
                    dist_2_closest_min = dist(closest_min, worker)
                    for mineral in minerals[1:]:
                        dist_2_min = dist(mineral, worker)
                        if dist_2_min < dist_2_closest_min:
                            closest_min = mineral
                            dist_2_closest_min = dist_2_min
                    worker.move((closest_min.x, closest_min.y))
                    worker.clear_task()
                    # print('go gather, lazy worker!')
                    worker.mineral_to_gather = closest_min
                    worker.task_x = closest_min.x
                    worker.task_y = closest_min.y
                    closest_min.workers.append(worker)
        except IndexError:
            pass
        # AI sending units to attack:
        for unit in enemy_units:
            if unit.weapon_type != 'none' and not unit.has_target_p:
                closest_enemy = None
                closest_enemy_dist = None
                for entity in our_units + our_structs:
                    try:
                        if not unit.attacks_air and entity.flying:
                            continue
                        if not unit.attacks_ground \
                                and not entity.flying:
                            continue
                    except AttributeError:
                        pass
                    dist_to_enemy = dist(unit, entity)
                    if not closest_enemy:
                        closest_enemy = entity
                        closest_enemy_dist = dist_to_enemy
                    else:
                        if dist_to_enemy < closest_enemy_dist:
                            closest_enemy = entity
                            closest_enemy_dist = dist_to_enemy
                try:
                    unit.move(round_coords(closest_enemy.x,
                                           closest_enemy.y))
                    unit.attack_moving = True
                except AttributeError:
                    pass


def main():
    game_window = PlanetEleven(SCREEN_W, SCREEN_H, SCREEN_TITLE)
    game_window.setup()
    pyglet.clock.schedule_interval(game_window.update, 1 / 60)
    pyglet.app.run()


if __name__ == "__main__":
    main()
