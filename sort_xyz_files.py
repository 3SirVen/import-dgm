import argparse
import glob
import os


def sort_and_check_xyz_file(file_path, check_for_km2):
    try:
        # Create a new file path with "sorted_" prefix
        folder, filename = os.path.split(file_path)
        sorted_file_path = os.path.join(folder, f"{filename}_sorted")

        if os.path.exists(sorted_file_path):
            # Skip files that have already been sorted
            return True

        # Copy the original file to the new file path
        with open(file_path, "r") as original_file:
            with open(sorted_file_path, "w") as sorted_file:
                sorted_file.write(original_file.read())

        with open(sorted_file_path, "r") as file:
            lines = file.readlines()

        # Remove any empty rows at the end
        while lines and lines[-1].strip() == "":
            lines.pop()

        # Check if the file has exactly 1,000,000 rows (1000m x 1000m grid with 1m resolution)
        if len(lines) != 1000000 and check_for_km2:
            print(
                f"File {sorted_file_path} has {len(lines)} rows instead of 1,000,000."
            )
            return False

        # Parse the lines into tuples of (x, y, z)
        coordinates = [tuple(map(float, line.split())) for line in lines]

        # Sort the coordinates first by y, then by x
        coordinates.sort(key=lambda coord: (coord[1], coord[0]))

        # Write the sorted coordinates back to the file
        with open(sorted_file_path, "w") as file:
            for coord in coordinates:
                file.write(f"{coord[0] // 1} {coord[1] // 1} {coord[2] // 1}\n")

        return True
    except Exception as e:
        print(f"An error occurred with file {file_path}: {e}")
        return False


def sort_all_xyz_files_in_folder(folder_path, check_for_km2=True, multiprocessing=True):
    # Get all .xyz files in the folder
    xyz_files = glob.glob(os.path.join(folder_path, "*.xyz"))

    results = []
    for file in xyz_files:
        results.append(sort_and_check_xyz_file(file, check_for_km2))

    # Print summary
    successful = sum(results)
    failed = len(results) - successful
    print(
        f"Sorting completed: {successful} files sorted successfully, {failed} files failed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sort and check .xyz files in a folder."
    )
    parser.add_argument(
        "folder", type=str, help="Path to the folder containing .xyz files."
    )
    args = parser.parse_args()

    sort_all_xyz_files_in_folder(args.folder)
