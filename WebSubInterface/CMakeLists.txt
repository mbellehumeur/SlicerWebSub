#-----------------------------------------------------------------------------
set(MODULE_NAME WebSubInterface)

set(MODULE_PYTHON_SCRIPTS
  WebSubInterface.py
  Lib/HubServer.py
  Lib/ImageDisplayClient.py
  Lib/ConferenceDialog.py
  Lib/hub_presets.py
  Lib/conference.py
  Lib/repo_paths.py
  Lib/__init__.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/WebSubInterface.svg
  Resources/Icons/WebSubInterfaceLogo.png
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  slicer_add_python_unittest(SCRIPT WebSubInterface.py)
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
