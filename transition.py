################################################################################
#                                                                              #
#                                MIT LICENSE                                   #
#                                ===========                                   #
#                                                                              #
# Copyright (C) 2014 Peter Varo (http://www.sketchandprototype.com)            #
#                                                                              #
# Permission is hereby granted, free of charge, to any person obtaining a copy #
# of this software and associated documentation files (the "Software"), to     #
# deal in the Software without restriction, including without limitation the   #
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or  #
# sell copies of the Software, and to permit persons to whom the Software is   #
# furnished to do so, subject to the following conditions:                     #
#                                                                              #
# The above copyright notice and this permission notice shall be included in   #
# all copies or substantial portions of the Software.                          #
#                                                                              #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR   #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,     #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE  #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER       #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING      #
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS #
# IN THE SOFTWARE.                                                             #
#                                                                              #
################################################################################

# Import Python modules
from math import pi
from json import load
from os.path import join, dirname
from string import ascii_lowercase
from itertools import chain, combinations

# Import Blender modules
import bpy

# Module information
bl_info = {'name'       : 'Transition Character to Character',
           'author'     : 'Peter Varo',
           'version'    : (1, 4, 4),
           'blender'    : (2, 70, 0),
           'location'   : 'View3D > Add > Mesh',
           'description': ('Generates all kinds of character to character '
                           'transitions based on existing blender data.'),
           'warning'    : '',
           'category'   : 'Add Mesh'}


#------------------------------------------------------------------------------#
def toascii(string):
    """
    Removes white space and non ASCII letters, and returns result.
    """
    # If string contains only ascii chars
    try:
        string.encode('ascii')
        # Remove all white spaces
        return ''.join(string.split())
    # If string contains other than ascii chars
    except UnicodeEncodeError:
        # Make it [A-Za-z] only
        A, z = ord('A'), ord('z')
        return ''.join(c if A <= ord(c) <= z else '' for c in chain(*string.split()))


#------------------------------------------------------------------------------#
def set_new_obj_properties(loop_type):
    """
    Function decorator for:
        - joining generated objects by the decorated function
        - bridgeing the edges loops in the joined mesh object
        - setting other properties, such as shading or origin point
    """
    # Create wrapper (decorator with arg)
    def main_wrapper(function):
        # Create new function (actual wrapper)
        def sub_wrapper(self, *args, **kwargs):
            # Call original function
            function(self, *args, **kwargs)
            # Join all selected objects into the selected active object
            bpy.ops.object.join()
            # Switch to edit mode and select all geometry
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            # Add edge loops
            bpy.ops.mesh.bridge_edge_loops(type=loop_type)
            # Add subdivision modifier and set its level and display mode
            bpy.ops.object.subdivision_set(level=self.subdsurf)
            bpy.context.object.modifiers['Subsurf'].show_only_control_edges = True
            # Switch back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
            # If transition was circular, then move origin point to 3D Cursor
            if self.circular:
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            # Set shaded mode to 'Smooth'
            bpy.ops.object.shade_smooth()
            # Deselect all objects
            bpy.context.scene.objects.active.select = False
        # Return new function
        return sub_wrapper
    # Return wrapper
    return main_wrapper


#------------------------------------------------------------------------------#
class TransitionCharToChar(bpy.types.Operator):
    """
    Character to character transition generator and tester blender operator.
    """
    # Basic info
    bl_idname  = "mesh.transition_char_to_char"
    bl_label   = "Transition Char to Char"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator GUI properties
    basetext = bpy.props.StringProperty(name='Text',
                                        default='jewellery',
                                        description='If not provided, operator '
                                                    'will build test transitions')
    distance = bpy.props.FloatProperty(name="Distance or Radius",
                                       default=2,
                                       min=.1, max=100,
                                       description='If operator is in test mode '
                                                   'and Circular property is OFF '
                                                   'this will be the distance '
                                                   'between the characters and/or '
                                                   'transitions. If Circular is ON '
                                                   'this will be the radius of the '
                                                   'arc or the full circle')
    circular = bpy.props.BoolProperty(name='Circular Transition',
                                      default=True,
                                      description='This switch will decide whether '
                                                  'generate the result(s) along a '
                                                  'linear or a circular path')
    transize = bpy.props.FloatProperty(name="Scale of Transition",
                                       default=1,
                                       min=.01, max=1,
                                       description='Sets the scale of the '
                                                   'transition characters')
    circsize = bpy.props.FloatProperty(name="Scale of Circle",
                                       default=1,
                                       min=.01, max=1,
                                       description='Sets the scale of the '
                                                   'circle character')
    subdsurf = bpy.props.IntProperty(name="Subdivision Level",
                                     default=3,
                                     min=0, max=6,
                                     description='Set the view level of the '
                                                 'Subdivision Surface modifier. '
                                                 'If set to 0 the subdivision '
                                                 'modifer will not be added')
    update_g = bpy.props.BoolProperty(name='Generator: Update',
                                      default=False,
                                      description='Regenerates the test results '
                                                  'with the new values provided. '
                                                  'It will only take effect if'
                                                  'the Text field is empty.')
    vars_col = bpy.props.IntProperty(name="Generator: Maximum Columns",
                                     default=15,
                                     min=0, max=26,
                                     description='Sets the maximum number of '
                                                 'variants horizontally (columns)')
    gap_unit = bpy.props.FloatProperty(name="Generator: Space Unit",
                                       default=3,
                                       min=.1, max=20,
                                       description='Sets the dimension of the '
                                                   'gab between the variants')
    min_char = bpy.props.IntProperty(name="Generator: Minimum Characters",
                                     default=4,
                                     min=3, max=360,
                                     description='Sets the minimum number of '
                                                 'characters in a full circle')

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def _dupobj(self, scene, name, copyobj):
        """
        Duplicates given object to a scene, and selects it.
        """
        # Create new object associated with a new mesh
        ob_new = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        # Copy data block from the old object into the new object
        ob_new.data = copyobj.data.copy()
        ob_new.scale = copyobj.scale
        ob_new.location = copyobj.location
        # Link new object to the given scene and select it
        scene.objects.link(ob_new)
        ob_new.select = True
        # Return new object
        return ob_new


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def _rotobj(self, scene, objects, location, radius, angle, axis):
        """
        Rotates all objects around the axis with the given angle.
        """
        x, y, z = location
        rotation = angle/len(objects)
        # Set Pivot point to 3D Cursor and place 3D Cursor
        bpy.context.space_data.pivot_point = 'CURSOR'
        scene.cursor_location = x + radius, y, z
        # Deselect all objects
        for obj in objects:
            obj.location = location
            obj.select = False
        # Rotate objects
        for i, obj in enumerate(objects):
            obj.select = True
            bpy.ops.transform.rotate(value=i*rotation, axis=axis)
            obj.select = False
        # Select all objects
        for obj in objects:
            obj.select = True


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @set_new_obj_properties('SINGLE')
    def _ctotc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        """
        Character to Transition to Circle to Transition to Character.
        """
        # Set local reference
        d = self.distance
        dup = self._dupobj
        # Get original objects
        trans1 = objects[char1][1]
        trans2 = objects[char2][1]
        # Duplicate objects
        nobj1  = dup(scene, obj1.name + '_', obj1)
        nobj2  = dup(scene, trans1.name + '_', trans1)
        circle = dup(scene, '{}->{}->(0)->{}->{}'.format(char1.upper(),
                                                         char1,
                                                         char2,
                                                         char2.upper()), objects[0][0])
        nobj3  = dup(scene, trans2.name + '_', trans2)
        nobj4  = dup(scene, obj2.name + '_', obj2)
        # Scale objects
        nobj2.scale  = nobj3.scale = (self.transize,)*3
        circle.scale = (self.circsize,)*3
        # If circular array
        if circular:
            # Rotate objects
            self._rotobj(scene    = scene,
                         objects  = (nobj1, nobj2, circle, nobj3, nobj4),
                         location = (x, 0, z),
                         radius   = d,
                         angle    = pi/(self.min_char/2)*1.25,
                         axis     = (0, 0, 1))
        # If linear array
        else:
            nobj1.location  = x, 0, z
            nobj2.location  = x, d, z
            circle.location = x, d*2, z
            nobj3.location  = x, d*3, z
            nobj4.location  = x, d*4, z
        # Set circle as the active object
        bpy.context.scene.objects.active = circle


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Interface for _ctoc()
    def _ct1oc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        self._ctoc(char1, char2, obj1, obj2, objects, x, z, scene, circular, False)

    # Interface for _ctoc()
    def _ct2oc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        self._ctoc(char1, char2, obj1, obj2, objects, x, z, scene, circular, True)

    @set_new_obj_properties('SINGLE')
    def _ctoc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular, reverse):
        """
        Character to Transition to Circle to Character.
        """
        # Set local reference
        d = self.distance
        dup = self._dupobj
        # Duplicate objects
        nobj1  = dup(scene, obj1.name + '_', obj1)
        nobj3  = dup(scene, obj2.name + '_', obj2)
        # If Character to Circle to Transition to Character
        if reverse:
            # Get original objects
            trans = objects[char2][1]
            # Duplicate objects
            circle = dup(scene, '{}->(0)->{}->{}'.format(char1.upper(),
                                                         char2,
                                                         char2.upper()), objects[0][0])
            nobj2  = dup(scene, trans.name + '_', trans)
            # Set up group and locations
            group = nobj1, circle, nobj2, nobj3
            loc = (x, d*2, z), (x, d, z)
        # If Character to Transition to Circle to Character
        else:
            # Get original objects
            trans = objects[char1][1]
            # Duplicate objects
            nobj2  = dup(scene, trans.name + '_', trans)
            circle = dup(scene, '{}->{}->(0)->{}'.format(char1.upper(),
                                                         char1,
                                                         char2.upper()), objects[0][0])
            # Set up group and locations
            group = nobj1, nobj2, circle, nobj3
            loc = (x, d, z), (x, d*2, z)
        # Scale objects
        nobj2.scale  = (self.transize,)*3
        circle.scale = (self.circsize,)*3
        # If circular array
        if circular:
            # Rotate objects
            self._rotobj(scene    = scene,
                         objects  = group,
                         location = (x, 0, z),
                         radius   = d,
                         angle    = pi/(self.min_char/2)*1.3333333333,
                         axis     = (0, 0, 1))
        # If linear array
        else:
            nobj1.location  = x, 0, z
            nobj2.location  = loc[0]
            circle.location = loc[1]
            nobj3.location  = x, d*3, z
        # Set circle as the active object
        bpy.context.scene.objects.active = circle


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Interface for _ctc()
    def _ct1c(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        self._ctc(char1, char2, obj1, obj2, objects, x, z, scene, circular, False)

    # Interface for _ctc()
    def _ct2c(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        self._ctc(char1, char2, obj1, obj2, objects, x, z, scene, circular, True)

    @set_new_obj_properties('SINGLE')
    def _ctc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular, reverse):
        """
        Character to Transition to Character.
        """
        # Set local reference
        d = self.distance
        dup = self._dupobj
        # Get original objects
        tchar = char2 if reverse else char1
        # Duplicate objects
        nobj1  = dup(scene, obj1.name + '_', obj1)
        nobj2  = dup(scene, '{}->{}->{}'.format(char1.upper(),
                                                tchar,
                                                char2.upper()), objects[tchar][1])
        nobj3  = dup(scene, obj2.name + '_', obj2)
        # Scale objects
        nobj2.scale  = (self.transize,)*3
        # If circular array
        if circular:
            # Rotate objects
            self._rotobj(scene    = scene,
                         objects  = (nobj1, nobj2, nobj3),
                         location = (x, 0, z),
                         radius   = d,
                         angle    = pi/(self.min_char/2)*1.5,
                         axis     = (0, 0, 1))
        # If linear array
        else:
            nobj1.location  = x, 0, z
            nobj2.location  = x, d, z
            nobj3.location  = x, d*2, z
        # Set circle as the active object
        bpy.context.scene.objects.active = nobj2


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @set_new_obj_properties('SINGLE')
    def _coc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        """
        Character to Circle to Character
        """
        # Set local reference
        d = self.distance
        dup = self._dupobj
        # Duplicate objects
        nobj1  = dup(scene, obj1.name + '_', obj1)
        circle = dup(scene, '{}->(0)->{}'.format(char1.upper(),
                                                 char2.upper()), objects[0][0])
        nobj2  = dup(scene, obj2.name + '_', obj2)
        # Scale objects
        circle.scale = (self.circsize,)*3
        # If circular array
        if circular:
            # Rotate objects
            self._rotobj(scene    = scene,
                         objects  = (nobj1, circle, nobj2),
                         location = (x, 0, z),
                         radius   = d,
                         angle    = pi/(self.min_char/2)*1.5,
                         axis     = (0, 0, 1))
        # If linear array
        else:
            nobj1.location  = x, 0, z
            circle.location = x, d, z
            nobj2.location  = x, d*2, z
        # Set circle as the active object
        bpy.context.scene.objects.active = circle


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @set_new_obj_properties('SINGLE')
    def _cc(self, char1, char2, obj1, obj2, objects, x, z, scene, circular):
        """
        Character to Character.
        """
        # Set local reference
        d = self.distance
        # Duplicate objects
        nobj1 = self._dupobj(scene, '{}->{}'.format(char1.upper(),
                                                    char2.upper()), obj1)
        nobj2 = self._dupobj(scene, obj2.name + '_', obj2)
        # If circular array
        if circular:
            # Rotate objects
            self._rotobj(scene    = scene,
                         objects  = (nobj1, nobj2),
                         location = (x, 0, z),
                         radius   = d,
                         angle    = pi/(self.min_char/2)*2,
                         axis     = (0, 0, 1))
        # If linear array
        else:
            # Move objects
            nobj1.location = x, 0, z
            nobj2.location = x, d, z
        # Set the first object as active
        bpy.context.scene.objects.active = nobj1


    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @set_new_obj_properties('CLOSED')
    def _ctrans(self, basetext, kerning, objects, scene):
        """
        Full circle transition based on the kerning table.
        """
        # Set local references
        d = self.distance
        basetext += basetext[0]
        group = []
        # Setup helper function
        def add(obj, args):
            args[0].append(obj)
        nobj = self._trans(basetext, kerning, objects, scene, add, [group])
        # Rotate objects
        self._rotobj(scene    = scene,
                     objects  = group,
                     location = (-d, 0, 0),
                     radius   = d,
                     angle    = 2*pi,
                     axis     = (0, 0, 1))
        # Name the last one and set it as active object
        nobj.name = basetext + '_circular_transition'
        bpy.context.scene.objects.active = nobj

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @set_new_obj_properties('SINGLE')
    def _ltrans(self, basetext, kerning, objects, scene):
        """
        Full linear transition based on the kerning table.
        """
        # Set local reference
        d = self.distance
        s = 0
        # Setup helper function
        def loc(obj, args):
            obj.location = 0, args[0], 0
            args[0] += args[1]
        # Create transition
        nobj = self._trans(basetext, kerning, objects, scene, loc, [s, d])
        # Name the last one and set it as active object
        nobj.name = basetext + '_linear_transition'
        bpy.context.scene.objects.active = nobj

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def _trans(self, basetext, kerning, objects, scene, function, args):
        """
        Creates a full transition "chain" based on the kerning table.
        """
        # Set local reference
        dup = self._dupobj
        cs = (self.circsize,)*3
        ts = (self.transize,)*3
        circle = objects[0][0]
        # Get characters from input text
        for i, (char1, char2) in enumerate(zip(basetext, basetext[1:])):
            # Get transition sequence
            try:
                steps = kerning[char1][char2]
            except KeyError:
                steps = kerning[char2][char1][::-1]
            # Create linear transition between characters
            for char in steps[bool(i):]:
                # If _start or _trans
                try:
                    # If transition
                    if char.islower():
                        # Get template object
                        obj = objects[char][1]
                        # Duplicate object
                        nobj = dup(scene, basetext + obj.name, obj)
                        # Scale transition
                        nobj.scale = ts
                    # If start/end character
                    else:
                        # Get template object
                        obj = objects[char.lower()][0]
                        # duplicate object
                        nobj = dup(scene, basetext + obj.name, obj)
                # If _circle
                except AttributeError:
                    # Duplicate segment
                    nobj = dup(scene, basetext + circle.name, circle)
                    # Scale circle
                    nobj.scale = cs
                # Call custom function on custom arg
                function(nobj, args)
        # Return last object
        return nobj

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def execute(self, context):
        """
        Blender executes operator.
        """
        # If __font__ scene is available
        try:
            bpy.data.scenes['__font__']
        # If __font__ scene does not exist
        # then name the current scene to it
        except KeyError:
            context.scene.name = '__font__'
        # Make sure area is in Object Mode, and deselect everything
        bpy.ops.object.mode_set(mode='OBJECT')
        for obj in bpy.data.objects:
            obj.select = False

        # Get essentials as local references
        basetext  = toascii(self.basetext.lower())
        space     = self.gap_unit
        vars_col  = self.vars_col * space
        circular  = self.circular
        functions = (self._cc, self._coc, self._ct1c, self._ct2c,
                     self._ct1oc, self._ct2oc, self._ctotc)

        # Get all character objects and their transitions and the circle object
        bdobjs = bpy.data.objects
        objects = {c:(bdobjs['{}_start'.format(c)],
                      bdobjs['{}_trans'.format(c)]) for c in ascii_lowercase}
        objects[0] = (bdobjs['_circle'],)*2

        # If generate complex text
        if basetext:
            # Open and load kerning table
            kerning = {}
            with open(join(dirname(bpy.data.filepath), 'kerning.json')) as f:
                kerning = load(f)
            # Create new scene for result if scene does not exist
            try:
                bpy.data.scenes[basetext]
            except KeyError:
                bpy.ops.scene.new()
                scene = bpy.context.scene
                scene.name = basetext
            # Generate transition pattern
            (self._ctrans if circular else self._ltrans)(basetext,
                                                         kerning,
                                                         objects,
                                                         scene)

        # If generate test cases
        elif self.update_g:
            variations = tuple(combinations(ascii_lowercase, 2))
            row = 0
            col = 0
            char = None
            allvar = len(variations)*len(functions)
            status = 1
            # Get the two characters
            for char1, char2 in reversed(variations):
                # Decide whether to start a new Scene or not
                # based on the first character the second one is combined to
                if char != char1:
                    try:
                        bpy.data.scenes[char1]
                    except KeyError:
                        bpy.ops.scene.new()
                        scene = bpy.context.scene
                        scene.name = char = char1
                        row = 0
                        col = 0
                    # Get the first original character object
                    obj1 = objects[char1][0]

                # Get the second original character object
                obj2 = objects[char2][0]
                # Generate the different transitions
                for fn in functions:
                    fn(char1, char2, obj1, obj2, objects, col, row, scene, circular)
                    # Increase column based on limit
                    col += space
                    if col >= vars_col:
                        row += space
                        col = 0
                    # Put status to stdout
                    print('STATUS: {:>4} / {}'.format(status, allvar))
                    status += 1

        # Deselect original objects
        for start, trans in objects.values():
            start.select = False
            trans.select = False

        # Turn on matcap and set material to matte metal
        context.space_data.use_matcap = True
        context.space_data.matcap_icon = '15'
        # Return if everything went fine
        return {'FINISHED'}


#------------------------------------------------------------------------------#
# Place operator in menu
def menu_func(self, context):
    self.layout.menu(TransitionCharToChar.bl_idname, icon='TEXT')

# Administration functions for blender: load and unload add-on
def register():
    bpy.utils.register_class(TransitionCharToChar)
    bpy.types.INFO_MT_mesh_add.append(menu_func)

def unregister():
    bpy.utils.unregister_class(TransitionCharToChar)

#------------------------------------------------------------------------------#
if __name__ == '__main__':
    # If loading this add-on, register operator
    register()
