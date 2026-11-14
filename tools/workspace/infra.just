# Shared controller entry points for nested infrastructure modules.
set positional-arguments

export SMARTHOME_WORKSPACE := clean(source_directory() / "../..")
workspace := SMARTHOME_WORKSPACE
workspace_python := quote(trim(read(workspace / ".python-version")))
workspace_just := "just --justfile " + quote(workspace / "Justfile") + " --working-directory " + quote(workspace)
wiki_run := quote(workspace / "wiki/run")
