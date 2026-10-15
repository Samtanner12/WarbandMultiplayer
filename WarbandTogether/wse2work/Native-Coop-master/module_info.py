
# Point export_dir to the folder you will be keeping your module
# Make sure you use forward slashes (/) and NOT backward slashes (\)

import os

# Keep compilation local; deployment is a separate, explicit operation.
export_dir = os.environ.get("WARBAND_EXPORT_DIR", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../build/Modules/NativeCoop")))
export_dir = export_dir.replace("\\", "/").rstrip("/") + "/"
#export_dir = "./output/"
