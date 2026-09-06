"""Select the Tcl/Tk data bundled with the Python used to build the app."""

from __future__ import annotations

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    tcl_library = bundle_dir / "python_tcl"
    tk_library = bundle_dir / "python_tk"
    if (tcl_library / "init.tcl").is_file():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
    if (tk_library / "tk.tcl").is_file():
        os.environ["TK_LIBRARY"] = str(tk_library)
