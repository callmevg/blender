"""Initialization for the beginner application template."""

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper, ImportHelper
from mathutils import Matrix


def beginner_workspace():
    return bpy.data.workspaces.get("Beginner") or bpy.data.workspaces.get("Layout")


def principled_material(obj, *, create=False):
    material = obj.active_material
    if material is None and create:
        material = bpy.data.materials.new(name="Material")
        obj.data.materials.append(material)
    if material is None:
        return None, None

    if material.node_tree is None:
        material.use_nodes = True
    shader = next(
        (node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'),
        None,
    )
    return material, shader


def update_factory_startup_workspaces():
    workspace = beginner_workspace()
    if workspace is not None:
        workspace.name = "Beginner"


def update_factory_startup_input():
    inputs = bpy.context.preferences.inputs
    inputs.use_multitouch_gestures = True
    inputs.use_mouse_emulate_3_button = True
    inputs.mouse_emulate_3_button_modifier = 'ALT'
    inputs.use_rotate_around_active = True
    inputs.use_zoom_to_mouse = True


def update_factory_startup_screens():
    workspace = beginner_workspace()
    if workspace is None:
        return

    for screen in workspace.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.show_region_ui = True
                space.show_region_toolbar = False
                space.shading.type = 'MATERIAL'


def close_beginner_timeline():
    if bpy.context.window is None:
        return 0.1

    screen = bpy.context.window.screen
    area = next((area for area in screen.areas if area.type == 'DOPESHEET_EDITOR'), None)
    bpy.app.timers.register(close_beginner_properties, first_interval=0.3)
    if area is not None:
        with bpy.context.temp_override(area=area):
            bpy.ops.screen.area_close()
    return None


def close_beginner_properties():
    if bpy.context.window is None:
        return 0.1

    screen = bpy.context.window.screen
    area = next((area for area in screen.areas if area.type == 'PROPERTIES'), None)
    bpy.app.timers.register(finalize_beginner_ui, first_interval=0.3)
    if area is not None:
        with bpy.context.temp_override(area=area):
            bpy.ops.screen.area_close()
    return None


def finalize_beginner_ui():
    workspace = beginner_workspace()
    retry = False
    if workspace is not None:
        for screen in workspace.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            try:
                                region.active_panel_category = "Beginner"
                            except AttributeError:
                                retry = True
                        elif region.type == 'WINDOW':
                            area.spaces.active.clip_start = 0.0001
                            area.spaces.active.region_3d.view_distance = 0.2
    return 0.1 if retry else None


def update_factory_startup_scenes():
    for scene in bpy.data.scenes:
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.length_unit = 'MILLIMETERS'
        scene.unit_settings.scale_length = 1.0
    bpy.data.batch_remove(
        ids=tuple(obj for obj in bpy.data.objects if obj.type in {'CAMERA', 'LIGHT'})
    )
    starter_cube = bpy.data.objects.get("Cube")
    if starter_cube is not None and starter_cube.type == 'MESH':
        for vertex in starter_cube.data.vertices:
            vertex.co *= 0.02


def update_advanced_visibility(_self, context):
    if not context.window_manager.beginner_show_advanced:
        workspace = bpy.data.workspaces.get("Beginner")
        if workspace is not None and context.window is not None:
            context.window.workspace = workspace


class BEGINNER_OT_add_bevel(Operator):
    bl_idname = "beginner.add_bevel"
    bl_label = "Round Edges"
    bl_description = "Add a small non-destructive bevel to the selected object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        modifier = obj.modifiers.new(name="Rounded Edges", type='BEVEL')
        modifier.width = max(min(obj.dimensions) * 0.04, 0.0005)
        modifier.segments = 3
        return {'FINISHED'}


class BEGINNER_OT_add_solidify(Operator):
    bl_idname = "beginner.add_solidify"
    bl_label = "Add Wall Thickness"
    bl_description = "Give an open surface printable wall thickness"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        modifier = context.object.modifiers.new(name="Wall Thickness", type='SOLIDIFY')
        modifier.thickness = 0.002
        return {'FINISHED'}


class BEGINNER_OT_add_subdivision(Operator):
    bl_idname = "beginner.add_subdivision"
    bl_label = "Smooth Surface"
    bl_description = "Smooth the selected mesh with a Subdivision Surface modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        modifier = context.object.modifiers.new(name="Smooth Surface", type='SUBSURF')
        modifier.levels = 2
        modifier.render_levels = 2
        return {'FINISHED'}


class BEGINNER_OT_apply_scale(Operator):
    bl_idname = "beginner.apply_scale"
    bl_label = "Apply Size"
    bl_description = "Apply object scale so bevels and exports use predictable dimensions"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.mode == 'OBJECT'

    def execute(self, context):
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return {'FINISHED'}


class BEGINNER_OT_restore_move(Operator):
    bl_idname = "beginner.restore_move"
    bl_label = "Restore Move"
    bl_description = "Unlock position axes and disable Affect Only Origins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.mode == 'OBJECT'

    def execute(self, context):
        context.object.lock_location = (False, False, False)
        context.scene.tool_settings.use_transform_data_origin = False
        if context.object.constraints:
            self.report({'WARNING'}, "Position unlocked; constraints may still limit movement")
        else:
            self.report({'INFO'}, "Move controls restored")
        return {'FINISHED'}


class BEGINNER_OT_add_material(Operator):
    bl_idname = "beginner.add_material"
    bl_label = "Add Material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        principled_material(context.object, create=True)
        return {'FINISHED'}


class BEGINNER_OT_add_color_texture(Operator, ImportHelper):
    bl_idname = "beginner.add_color_texture"
    bl_label = "Choose Color Texture"
    bl_description = "Connect an image to the material base color"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff",
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        material, shader = principled_material(context.object, create=True)
        if shader is None:
            self.report({'ERROR'}, "Material has no Principled BSDF shader")
            return {'CANCELLED'}

        image = bpy.data.images.load(self.filepath, check_existing=True)
        texture = material.node_tree.nodes.get("Beginner Color Texture")
        if texture is None:
            texture = material.node_tree.nodes.new('ShaderNodeTexImage')
            texture.name = "Beginner Color Texture"
        texture.image = image
        material.node_tree.links.new(shader.inputs["Base Color"], texture.outputs["Color"])
        return {'FINISHED'}


class BEGINNER_OT_check_print(Operator):
    bl_idname = "beginner.check_print"
    bl_label = "Check for 3D Printing"
    bl_description = "Check the selected mesh for open or non-manifold edges"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        mesh = bmesh.new()
        mesh.from_mesh(context.object.data)
        invalid_edges = sum(not edge.is_manifold for edge in mesh.edges)
        mesh.free()

        if invalid_edges:
            self.report({'WARNING'}, f"Found {invalid_edges} open or non-manifold edges")
        else:
            self.report({'INFO'}, "Mesh is closed and manifold")
        return {'FINISHED'}


class BEGINNER_OT_export_glb(Operator, ExportHelper):
    bl_idname = "beginner.export_glb"
    bl_label = "Export Website Model"
    bl_description = "Export selected objects as a correctly scaled GLB website model"

    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_objects = set(context.selected_objects)
        root_objects = [obj for obj in selected_objects if obj.parent not in selected_objects]
        original_matrices = [(obj, obj.matrix_world.copy()) for obj in root_objects]

        unit_scale = context.scene.unit_settings.scale_length
        scale_matrix = Matrix.Scale(unit_scale, 4)
        try:
            for obj, matrix in original_matrices:
                obj.matrix_world = scale_matrix @ matrix
            return bpy.ops.export_scene.gltf(
                filepath=self.filepath,
                export_format='GLB',
                use_selection=True,
                export_animations=False,
                export_cameras=False,
                export_lights=False,
            )
        finally:
            for obj, matrix in original_matrices:
                obj.matrix_world = matrix


class BEGINNER_PT_start_here(Panel):
    bl_idname = "BEGINNER_PT_start_here"
    bl_label = "Start Here"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Beginner"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        create = layout.box()
        create.label(text="Create", icon='ADD')
        row = create.row(align=True)
        row.operator("mesh.primitive_cube_add", text="Box", icon='MESH_CUBE').size = 0.04
        cylinder = row.operator("mesh.primitive_cylinder_add", text="Cylinder", icon='MESH_CYLINDER')
        cylinder.radius = 0.02
        cylinder.depth = 0.04
        create.operator("mesh.primitive_uv_sphere_add", text="Sphere", icon='MESH_UVSPHERE').radius = 0.02

        if obj is None or obj.type != 'MESH':
            layout.label(text="Select a mesh to continue", icon='INFO')
            return

        size = layout.box()
        size.label(text="Size", icon='ORIENTATION_GLOBAL')
        position = size.row(align=True)
        position.prop(obj, "location", text="Position")
        position.prop(obj, "lock_location", text="", emboss=False, icon='DECORATE_UNLOCKED')
        size.prop(obj, "dimensions", text="Dimensions")
        row = size.row(align=True)
        row.operator("transform.translate", text="Move", icon='TRANSFORM_MOVE')
        row.operator("beginner.restore_move", text="Restore Move", icon='UNLOCKED')
        size.operator("beginner.apply_scale", icon='CHECKMARK')

        shape = layout.box()
        shape.label(text="Shape", icon='MODIFIER')
        if obj.mode == 'OBJECT':
            row = shape.row(align=True)
            row.operator("beginner.add_bevel", text="Round Edges")
            row.operator("beginner.add_solidify", text="Wall Thickness")
            subdivision = next(
                (modifier for modifier in obj.modifiers if modifier.type == 'SUBSURF'),
                None,
            )
            if subdivision is None:
                shape.operator("beginner.add_subdivision", text="Smooth Surface")
            else:
                row = shape.row(align=True)
                row.prop(subdivision, "show_viewport", text="Smooth", toggle=True)
                row.prop(subdivision, "levels", text="Level")
            shape.operator("object.editmode_toggle", text="Edit Shape", icon='EDITMODE_HLT')
        else:
            row = shape.row(align=True)
            row.operator("mesh.extrude_region_move", text="Extrude")
            row.operator("mesh.inset", text="Inset")
            shape.operator("mesh.bevel", text="Bevel")
            shape.operator("object.editmode_toggle", text="Finish Editing", icon='OBJECT_DATAMODE')

        material_box = layout.box()
        material_box.label(text="Surface", icon='MATERIAL')
        material, shader = principled_material(obj)
        if shader is None:
            material_box.operator("beginner.add_material", icon='ADD')
        else:
            material_box.prop(shader.inputs["Base Color"], "default_value", text="Color")
            material_box.prop(shader.inputs["Metallic"], "default_value", text="Metallic")
            material_box.prop(shader.inputs["Roughness"], "default_value", text="Roughness")
            material_box.operator("beginner.add_color_texture", icon='IMAGE_DATA')

        finish = layout.box()
        finish.label(text="Finish", icon='EXPORT')
        finish.operator("beginner.check_print", icon='CHECKMARK')
        if bpy.app.build_options.io_stl:
            stl = finish.operator("wm.stl_export", text="3D Print (.stl)", icon='EXPORT')
            stl.export_selected_objects = True
            stl.apply_modifiers = True
            stl.global_scale = 1000.0
        finish.operator("beginner.export_glb", text="Website Model (.glb)", icon='EXPORT')

@persistent
def load_handler(_):
    bpy.context.preferences.view.show_splash = False
    update_factory_startup_workspaces()
    update_factory_startup_input()
    update_factory_startup_scenes()
    if not bpy.app.background:
        update_factory_startup_screens()
        bpy.app.timers.register(close_beginner_timeline, first_interval=0.5)


classes = (
    BEGINNER_OT_add_bevel,
    BEGINNER_OT_add_solidify,
    BEGINNER_OT_add_subdivision,
    BEGINNER_OT_apply_scale,
    BEGINNER_OT_restore_move,
    BEGINNER_OT_add_material,
    BEGINNER_OT_add_color_texture,
    BEGINNER_OT_check_print,
    BEGINNER_OT_export_glb,
    BEGINNER_PT_start_here,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.beginner_show_advanced = BoolProperty(
        name="Advanced",
        description="Show Blender's advanced workspaces",
        default=False,
        update=update_advanced_visibility,
    )
    bpy.app.handlers.load_factory_startup_post.append(load_handler)


def unregister():
    bpy.app.handlers.load_factory_startup_post.remove(load_handler)
    for timer in (
        close_beginner_timeline,
        close_beginner_properties,
        finalize_beginner_ui,
    ):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    del bpy.types.WindowManager.beginner_show_advanced
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)