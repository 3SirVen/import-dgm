import os
import re
from operator import itemgetter

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy_extras.io_utils import ImportHelper


def get_coordinates_from_file(
    filename, delimiter, ignore_rows, ignore_columns, scale, origin
):
    with open(filename, "r") as file:
        lines = file.readlines()

    # Check if all origin coordinates are floats
    if not all(isinstance(o, float) for o in origin):
        print(origin)
        for o in origin:
            print(type(o))
        raise ValueError("Origin coordinates must be floats")

    # Read and sort the vertices coordinates (sort by x and y)
    vertices = sorted(
        [
            (
                (float(re.split(delimiter, r.strip())[0]) - origin[0]) * scale,
                (float(re.split(delimiter, r.strip())[1]) - origin[1]) * scale,
                (float(re.split(delimiter, r.strip())[2]) - origin[2]) * scale,
            )
            for r in lines
        ],
        key=itemgetter(0, 1),
    )

    if len(vertices) < 2:
        raise ValueError("Not enough vertices to determine xSize")

    xSize = (
        next(
            i for i in range(len(vertices) - 1) if vertices[i][0] != vertices[i + 1][0]
        )
        + 1
    )
    ySize = len(vertices) // xSize

    print(f"xSize: {xSize}")
    print(f"ySize: {ySize}")

    # Filter rows and columns
    filtered_vertices = [
        vertex
        for i, vertex in enumerate(vertices)
        if (i // xSize) % ignore_rows == 0 and (i % xSize) % ignore_columns == 0
    ]

    filtered_xSize = xSize // ignore_columns
    filtered_ySize = ySize // ignore_rows

    print(f"Filtered xSize: {filtered_xSize}")
    print(f"Filtered ySize: {filtered_ySize}")

    return filtered_vertices, filtered_xSize, filtered_ySize


def create_polygon_mesh(vertices, xSize, ySize, ob_name):
    # Generate the polygons
    polygons = []
    for i in range(ySize - 1):
        for j in range(xSize - 1):
            polygons.append(
                (
                    i * xSize + j,
                    i * xSize + j + 1,
                    (i + 1) * xSize + j + 1,
                    (i + 1) * xSize + j,
                )
            )

    name = ob_name
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)

    obj.data.from_pydata(vertices, [], polygons)  # Associate vertices and polygons

    obj.scale = (1, 1, 1)
    for p in obj.data.polygons:  # Set smooth shading
        p.use_smooth = True

    bpy.context.collection.objects.link(obj)  # Link the object to the collection

    mat = bpy.data.materials.new(name="DGM_Material")
    mat.specular_intensity = 0.0
    mat.roughness = 1

    obj.data.materials.append(mat)

    mesh.update(calc_edges=True)

    return mesh


def main(
    filename,
    scale,
    origin,
    coordinate_system,
    ignore_rows,
    ignore_columns,
):
    print(f"Importing {filename}")
    print(f"Scale: {scale}")
    print(f"Origin: {origin}")
    print(f"Coordinate System: {coordinate_system}")
    print(f"Ignore Rows: {ignore_rows}")
    print(f"Ignore Columns: {ignore_columns}")

    # Distinguish between different file types
    if filename.endswith(".xyz") or filename.endswith(".txt"):
        delimiter = " "
        vertices, xSize, ySize = get_coordinates_from_file(
            filename,
            delimiter,
            ignore_rows,
            ignore_columns,
            scale,
            origin,
        )

        ob_name = os.path.basename(filename)

        create_polygon_mesh(vertices, xSize, ySize, ob_name)
    elif filename.endswith(".tif"):
        raise NotImplementedError("TIFF files are not supported yet")
    else:
        raise ValueError("Invalid file type")


class DGMDirectorySelector(bpy.types.Operator, ImportHelper):
    """Operator to select and import DGM files."""

    bl_idname = "wm.dgm_folder_selector"
    bl_label = "Import cityGML file(s)"

    filename_ext = ".xyz, .txt, .tif"
    use_filter_folder = True
    filter_glob: StringProperty(default="*.xyz;*.txt;*.tif", options={"HIDDEN"})  # type: ignore

    files: CollectionProperty(name="File Path", type=bpy.types.OperatorFileListElement)  # type: ignore
    scale_setting: FloatProperty(
        name="Set Scale",
        description="Set the scale at which the data should be imported",
        soft_min=0.0,
        soft_max=1.0,
        precision=3,
        default=1.0,
    )  # type: ignore
    origin_setting_x: FloatProperty(
        name="Origin Point X",
        description="Set the X coordinate of the origin point you want to use for the data",
        precision=1,
        default=0.0,
    )  # type: ignore
    origin_setting_y: FloatProperty(
        name="Origin Point Y",
        description="Set the Y coordinate of the origin point you want to use for the data",
        precision=1,
        default=0.0,
    )  # type: ignore
    origin_setting_z: FloatProperty(
        name="Origin Point Z",
        description="Set the Z coordinate of the origin point you want to use for the data",
        precision=1,
        default=0.0,
    )  # type: ignore
    coordinate_system: EnumProperty(
        name="Coordinate System",
        description="Select the coordinate system of the data",
        items=(("epsg:25832", "EPSG:25832", "EPSG:25832 coordinate system"),),
    )  # type: ignore
    limit_data: BoolProperty(
        name="Limit Data by ignoring rows and/or columns",
        description="Since it might be a large dataset, you can limit the data by ignoring rows and/or columns",
        default=False,
    )  # type: ignore
    ignore_rows: IntProperty(
        name="Ignore Rows",
        description="Only select every nth row",
        min=1,
        default=1,
    )  # type: ignore
    ignore_columns: IntProperty(
        name="Ignore Columns",
        description="Only select every nth column",
        min=1,
        default=1,
    )  # type: ignore

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Origin Point (X,Y,Z):")
        row = box.row(align=True)
        row.prop(self, "origin_setting_x", text="X:")
        row = box.row(align=True)
        row.prop(self, "origin_setting_y", text="Y:")
        row = box.row(align=True)
        row.prop(self, "origin_setting_z", text="Z:")

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Import Scale:")
        row.prop(self, "scale_setting", text="")

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Coordinate System:")
        row.prop(self, "coordinate_system", text="")

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Limit Data:")
        row.prop(self, "limit_data", text="")

        if self.limit_data:
            row = box.row(align=True)
            row.prop(self, "ignore_rows", text="Ignore Rows")
            row = box.row(align=True)
            row.prop(self, "ignore_columns", text="Ignore Columns")

    def execute(self, context):
        folder = os.path.dirname(self.filepath)

        for i, file in enumerate(self.files):
            print(f"File {i + 1}/{len(self.files)}: {file.name}")
            path_to_file = os.path.join(folder, file.name)
            try:
                main(
                    filename=path_to_file,
                    scale=self.scale_setting,
                    origin=(
                        self.origin_setting_x,
                        self.origin_setting_y,
                        self.origin_setting_z,
                    ),
                    coordinate_system=self.coordinate_system,
                    ignore_rows=self.ignore_rows,
                    ignore_columns=self.ignore_columns,
                )
                self.report({"INFO"}, f"{file.name} imported")
                print(f"{file.name} imported")
            except Exception as e:
                self.report({"ERROR"}, f"Error importing {file.name}: {e}")
                print(f"Error importing {file.name}: {e}")
                return {"CANCELLED"}
        return {"FINISHED"}


def menu_import(self, context):
    self.layout.operator(DGMDirectorySelector.bl_idname, text="DGM (.xyz, .txt, .tif)")


def register():
    bpy.utils.register_class(DGMDirectorySelector)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(DGMDirectorySelector)


if __name__ == "__main__":
    register()
