#-----------------------------------------------------------------------------
set(MODULE_NAME WebSubInterface)

set(MODULE_PYTHON_SCRIPTS
  WebSubInterface.py
  Lib/HubServer.py
  Lib/ImageDisplayClient.py
  Lib/ConferenceDialog.py
  Lib/hub_presets.py
  Lib/conference.py
  Lib/python_deps.py
  Lib/repo_paths.py
  Lib/__init__.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/WebSubInterface.svg
  Resources/Icons/WebSubInterfaceLogo.png
  Resources/requirements.txt
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  # Offline hub / image_display / python_client scripts registered as CTest
  # (Testing/Python/CMakeLists.txt). Live hub smokes stay manual — see Testing/README.md.
  add_subdirectory(Testing)
endif()

#-----------------------------------------------------------------------------
# Bundle standalone components under the installed module directory.
set(_HUB_MOD_DIR "${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/WebSubInterface")

set(_HUB_INSTALL_EXCLUDES
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
  PATTERN "*.pyo" EXCLUDE
  PATTERN "worklist-example" EXCLUDE
  PATTERN "OHIF-client" EXCLUDE
  PATTERN "slim" EXCLUDE
  PATTERN "deploy" EXCLUDE
  PATTERN "samples" EXCLUDE
  PATTERN "slicer-hub.zip" EXCLUDE
  PATTERN "nifti" EXCLUDE
  PATTERN "worklist-client" EXCLUDE
  PATTERN "reporting-client" EXCLUDE
  PATTERN "classroom-client" EXCLUDE
  PATTERN "slicerlive" EXCLUDE
  PATTERN "slicer-mirror" EXCLUDE
  PATTERN "website" EXCLUDE
  PATTERN "scripts" EXCLUDE
  PATTERN "Dockerfile*" EXCLUDE
  PATTERN "make_zip.py" EXCLUDE
  PATTERN "deploy*.sh" EXCLUDE
  )

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/hub/"
        DESTINATION "${_HUB_MOD_DIR}/hub"
        ${_HUB_INSTALL_EXCLUDES}
        )

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/python_client/"
        DESTINATION "${_HUB_MOD_DIR}/python_client"
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        )



install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/image_display/lib"
        DESTINATION "${_HUB_MOD_DIR}/image_display"
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        )

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/image_display/run_image_display.py"
        DESTINATION "${_HUB_MOD_DIR}/image_display"
        )
