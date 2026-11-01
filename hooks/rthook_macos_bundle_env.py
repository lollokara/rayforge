import os
import sys

# The macOS bundle is started directly through its CFBundleExecutable.
# macOS only treats a process as the app, and only then offers the Local
# Network permission, when it is that executable, so there is no wrapper
# script that could export these paths before the interpreter starts.
if sys.platform == "darwin" and getattr(sys, "frozen", False):
    _macos_dir = os.path.dirname(os.path.abspath(sys.executable))
    _contents = os.path.dirname(_macos_dir)
    os.environ["GI_TYPELIB_PATH"] = os.path.join(
        _contents, "Resources", "gi_typelibs"
    )
    os.environ["GIO_EXTRA_MODULES"] = os.path.join(
        _contents, "Frameworks", "gio_modules"
    )
