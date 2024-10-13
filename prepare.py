import os
import zipfile

VERSION = (1, 0, 0)

ZIP_NAME = "ImportDGM"
FILES_AND_FOLDERS = [
    "./__init__.py",
    "./README.md",
    "./LICENSE",
    "./blender_manifest.toml",
    "./sort_xyz_files.py",
    "./convert_TIF_to_XYZ.py",
]
ROOT_DIR = "Import DGM"


def create_zip_archive(output_filename, items_to_include, root_dir):
    """
    Create a zip archive containing specific files and folders under a root directory.

    :param output_filename: The name of the output zip file.
    :param items_to_include: A list of files and folders to include in the zip archive.
    :param root_dir: The root directory name to use inside the zip archive.
    """
    with zipfile.ZipFile(
        "./releases/" + output_filename, "w", zipfile.ZIP_DEFLATED
    ) as zipf:
        for item in items_to_include:
            if os.path.isfile(item):
                arcname = os.path.join(
                    root_dir,
                    os.path.relpath(item, os.path.dirname(items_to_include[0])),
                )
                zipf.write(item, arcname)
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(
                            root_dir,
                            os.path.relpath(
                                file_path, os.path.dirname(items_to_include[0])
                            ),
                        )
                        zipf.write(file_path, arcname)


if __name__ == "__main__":
    version_str = ".".join(map(str, VERSION))
    output_filename = f"{ZIP_NAME}-{version_str}.zip"
    create_zip_archive(output_filename, FILES_AND_FOLDERS, ROOT_DIR)
