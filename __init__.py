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

from . import convert_TIF_to_XYZ, sort_xyz_files

try:
    from pyproj import CRS, Transformer
except ImportError:
    import subprocess
    import sys

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "rasterio"], stdout=subprocess.DEVNULL
    )
    from pyproj import CRS, Transformer

bl_info = {
    "name": "Import DGM",
    "description": "Import digital ground models (DGM)",
    "author": "3SirVen",
    "version": (1, 0, 1),
    "blender": (4, 2, 0),
    "doc_url": "https://github.com/3SirVen/import-dgm",
    "support": "COMMUNITY",
    "category": "Import-Export",
}


def calculate_size(vertices):
    xSize = (
        next(
            i for i in range(len(vertices) - 1) if vertices[i][0] != vertices[i + 1][0]
        )
        + 1
    )
    ySize = len(vertices) // xSize

    return xSize, ySize


def convert_utm_32_to_33(coordinate):
    utm_32 = CRS("epsg:25832")
    utm_33 = CRS("epsg:25833")
    transformer = Transformer.from_crs(utm_32, utm_33, always_xy=True)
    new_coordinate = transformer.transform(coordinate[0], coordinate[1])
    return (new_coordinate[0], new_coordinate[1], coordinate[2])


def get_coordinates_from_file(filename, ignore_rows, ignore_columns, scale, origin):
    if filename.split("_")[1] == "33":
        origin = convert_utm_32_to_33(origin)

    # Find delimiter by searching for the first character that is not a valid character in a float
    with open(filename, "r") as file:
        delimiter = next(
            (char for char in file.readline() if char not in "0123456789.-"), None
        )

    if not delimiter:
        raise ValueError("Could not determine delimiter")

    xSize = 0
    lines = []
    currentY = 0
    with open(filename, "r") as file:
        for i, line in enumerate(file):
            if i == 0:
                currentY = float(re.split(delimiter, line.strip())[1])
            elif currentY != float(re.split(delimiter, line.strip())[1]):
                xSize = i
                break

        if xSize == 0:
            raise ValueError("Could not determine xSize")

        file.seek(0)  # Reset file pointer to the beginning
        for i, line in enumerate(file):
            if (i // xSize) % ignore_rows == 0:
                if (i % xSize) % ignore_columns == 0:
                    lines.append(line)

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

    xSize, ySize = calculate_size(vertices)

    return vertices, xSize, ySize


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

    # Create UV map
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1, scale_to_bounds=True, correct_aspect=True)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Flip Normals
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh.update(calc_edges=True)

    return mesh


def find_all_vertices_on_edges(vertices, search_x_fixed, fixed_coordinate, min, max):
    if search_x_fixed:
        return [
            vertex
            for vertex in vertices
            if vertex[0] == fixed_coordinate and vertex[1] >= min and vertex[1] <= max
        ]
    else:
        return [
            vertex
            for vertex in vertices
            if vertex[1] == fixed_coordinate and vertex[0] >= min and vertex[0] <= max
        ]


def find_entry_by_x_and_y(vertices, x, y):
    for vertex in vertices:
        if vertex[0] == x and vertex[1] == y:
            return vertex

    return None


def find_closest_edges(vertices, edges, x_size, y_size):
    if not vertices or not edges:
        raise ValueError("Vertices and edges must not be empty")

    if not isinstance(vertices[0], (list, tuple)) or not isinstance(
        edges[0], (list, tuple)
    ):
        raise ValueError("Vertices and edges must be lists of tuples or lists")

    # Initialize closest_x and closest_y with negative infinity
    closest_x = float("-inf")
    closest_y = float("-inf")

    closest_x_tuple = (float("-inf"), float("-inf"))
    closest_y_tuple = (float("-inf"), float("-inf"))

    for edge in edges:
        if edge[0] <= vertices[0][0] and edge[0] >= closest_x:
            if edge[1] >= closest_x_tuple[1] and edge[1] <= vertices[x_size - 1][1]:
                closest_x = edge[0]
                closest_x_tuple = edge

        if edge[1] < vertices[0][1] and edge[1] >= closest_y:
            if edge[0] >= closest_y_tuple[0] and edge[0] <= vertices[-1][0]:
                closest_y = edge[1]
                closest_y_tuple = edge

    all_vertices_on_closest_x = []
    if closest_x != float("-inf"):
        all_vertices_on_closest_x = find_all_vertices_on_edges(
            edges, True, closest_x, vertices[0][1], closest_x_tuple[1]
        )

    all_vertices_on_closest_y = []
    if closest_y != float("-inf"):
        all_vertices_on_closest_y = find_all_vertices_on_edges(
            edges, False, closest_y, vertices[0][0], closest_y_tuple[0]
        )

    combined_closest = find_entry_by_x_and_y(edges, closest_x, closest_y)

    return all_vertices_on_closest_x, all_vertices_on_closest_y, combined_closest


def process_file(
    path_to_file, edges, all_vertices, ignore_rows, ignore_columns, scale, origin
):
    vertices, file_xSize, file_ySize = get_coordinates_from_file(
        path_to_file,
        ignore_rows,
        ignore_columns,
        scale,
        origin,
    )

    try:
        vertices_on_x, vertices_on_y, combined_closest = find_closest_edges(
            vertices, edges, file_xSize, file_ySize
        )
    except Exception as e:
        print(f"Error finding closest edges: {e}")
        vertices_on_x, vertices_on_y = [], []
        combined_closest = None

    # Add all vertices along the edges to the list
    for i in range(file_xSize):
        edges.append(vertices[i])
        edges.append(vertices[file_xSize * (file_ySize - 1) + i])
    for i in range(file_ySize):
        edges.append(vertices[i * file_xSize])
        edges.append(vertices[i * file_xSize + file_xSize - 1])

    if vertices_on_x:
        vertices.extend(vertices_on_x)
        file_xSize += 1
    if vertices_on_y:
        vertices.extend(vertices_on_y)
        file_ySize += 1
    if combined_closest:
        vertices.append(combined_closest)

    vertices = sorted(vertices, key=itemgetter(0, 1))

    all_vertices.extend(vertices)


def main(
    files,
    folder,
    scale,
    origin,
    coordinate_system,
    ignore_rows,
    ignore_columns,
):
    # Sort all files by name
    files = sorted(list(files), key=lambda x: x.name)

    edges = []

    all_vertices = []

    for i, file in enumerate(files):
        try:
            print(f"File {i + 1}/{len(files)}: {file.name}")
            path_to_file = os.path.join(folder, file.name)

            # Distinguish between different file types
            if path_to_file.endswith(".xyz") or path_to_file.endswith(".txt"):
                process_file(
                    path_to_file,
                    edges,
                    all_vertices,
                    ignore_rows,
                    ignore_columns,
                    scale,
                    origin,
                )

            elif path_to_file.endswith(".tif"):
                convert_TIF_to_XYZ.process_path(path_to_file)

                xyz_path = path_to_file.replace(".tif", ".xyz")

                process_file(
                    xyz_path,
                    edges,
                    all_vertices,
                    ignore_rows,
                    ignore_columns,
                    scale,
                    origin,
                )
            else:
                raise ValueError("Invalid file type")
        except Exception as e:
            print(f"Error importing {file.name}: {e} at {e.__traceback__.tb_lineno}")
            continue

    all_vertices = sorted(all_vertices, key=itemgetter(0, 1))
    # Remove duplicates
    all_vertices = [
        all_vertices[i]
        for i in range(len(all_vertices))
        if i == 0 or all_vertices[i] != all_vertices[i - 1]
    ]

    try:
        create_polygon_mesh(
            all_vertices,
            calculate_size(all_vertices)[0],
            calculate_size(all_vertices)[1],
            "All",
        )
    except Exception as e:
        print(f"Error creating mesh for all vertices: {e}")
        return


class DGMDirectorySelector(bpy.types.Operator, ImportHelper):
    """Operator to select and import DGM files."""

    bl_idname = "import_create.dgm"
    bl_label = "Import Digital Ground Models file(s)"

    filename_ext = ".xyz, .txt, .tif"
    use_filter_folder = True
    filter_glob: StringProperty(default="*.xyz;*.txt;*.tif", options={"HIDDEN"})  # type: ignore

    files: CollectionProperty(name="File Path", type=bpy.types.OperatorFileListElement)  # type: ignore
    scale: FloatProperty(
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
        default=530000.0,
    )  # type: ignore
    origin_setting_y: FloatProperty(
        name="Origin Point Y",
        description="Set the Y coordinate of the origin point you want to use for the data",
        precision=1,
        default=6036000.0,
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
        description="Since it might be a large dataset, you can limit the data by ignoring rows and/or columns. CAUTION: Disabling this option might lead to performance issues and/or crashes",
        default=True,
    )  # type: ignore
    ignore_rows: IntProperty(
        name="Ignore Rows",
        description="Only select every nth row",
        min=1,
        default=10,
    )  # type: ignore
    ignore_columns: IntProperty(
        name="Ignore Columns",
        description="Only select every nth column",
        min=1,
        default=10,
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
        row.prop(self, "scale", text="")

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

        print(f"Sorting XYZ files in folder {folder}")

        try:
            sort_xyz_files.sort_all_xyz_files_in_folder(
                folder_path=folder, check_for_km2=True, multiprocessing=False
            )
        except Exception as e:
            self.report({"ERROR"}, f"Error sorting XYZ files: {e}")
            print(f"Error sorting XYZ files: {e}")
            return {"CANCELLED"}

        print(f"Importing DGM files from folder {folder}")

        try:
            main(
                files=self.files,
                folder=folder,
                scale=self.scale,
                origin=(
                    self.origin_setting_x,
                    self.origin_setting_y,
                    self.origin_setting_z,
                ),
                coordinate_system=self.coordinate_system,
                ignore_rows=self.ignore_rows,
                ignore_columns=self.ignore_columns,
            )
            self.report({"INFO"}, f"{len(self.files)} files imported successfully")
            print(f"{len(self.files)} files imported successfully")
        except Exception as e:
            self.report({"ERROR"}, f"Error importing: {e}")
            print(f"Error importing: {e}")
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
