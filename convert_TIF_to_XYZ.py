import os
import sys
from multiprocessing import Pool, cpu_count

import rasterio
from pyproj import CRS, Transformer
from tqdm import tqdm


def convert_tif_to_xyz(tif_path, xyz_path):
    # Open the .tif file
    with rasterio.open(tif_path) as src:
        # Read the height data
        height_data = src.read(1)
        # Get the affine transform for the dataset
        transform_affine = src.transform
        # Define the source and destination coordinate systems
        src_crs = CRS.from_wkt(src.crs.to_wkt())
        dst_crs = CRS.from_epsg(25832)  # UTM zone 32N
        transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

        coordinates = []

        # Iterate over the rows and columns of the height data with a progress bar
        for row in tqdm(
            range(height_data.shape[0]), desc=f"Processing {os.path.basename(tif_path)}"
        ):
            for col in range(height_data.shape[1]):
                # Get the x, y coordinates in the source CRS
                x, y = transform_affine * (col, row)
                # Transform the coordinates to UTM 32
                utm_x, utm_y = transformer.transform(x, y)
                # Get the height value
                height = height_data[row, col]
                # Store the data in the list
                coordinates.append((utm_x, utm_y, height))

        # Sort the coordinates
        coordinates.sort(key=lambda coord: (coord[1], coord[0]))

        # Write the sorted data to the .xyz file
        with open(xyz_path, "w") as xyz_file:
            for coord in coordinates:
                xyz_file.write(f"{coord[0]} {coord[1]} {coord[2]}\n")

            # Remove the last newline character
            xyz_file.seek(xyz_file.tell() - 1)
            xyz_file.truncate()


def process_file(tif_path):
    xyz_path = tif_path.replace(".tif", ".xyz")
    convert_tif_to_xyz(tif_path, xyz_path)


def process_path(path):
    if os.path.isfile(path):
        if path.endswith(".tif"):
            process_file(path)
        else:
            print(f"File {path} is not a .tif file.")
    elif os.path.isdir(path):
        tif_files = [
            os.path.join(path, f) for f in os.listdir(path) if f.endswith(".tif")
        ]
        with Pool(round(cpu_count() / 2)) as pool:
            for _ in tqdm(
                pool.imap_unordered(process_file, tif_files),
                total=len(tif_files),
                desc="Processing directory",
            ):
                pass
    else:
        print(f"Path {path} is neither a file nor a directory.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert.py <path>")
    else:
        process_path(sys.argv[1])
