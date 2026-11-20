# Offline exit-code scripts (no Slicer GUI, no live hub). Live smokes stay manual —
# see Testing/README.md (smoke_hub_http, smoke_client_pubsub, run_live_smokes).

find_package(Python3 COMPONENTS Interpreter QUIET)
if(NOT Python3_EXECUTABLE AND DEFINED PYTHON_EXECUTABLE)
  set(Python3_EXECUTABLE "${PYTHON_EXECUTABLE}")
endif()
if(NOT Python3_EXECUTABLE AND DEFINED Slicer_PYTHON_EXECUTABLE)
  set(Python3_EXECUTABLE "${Slicer_PYTHON_EXECUTABLE}")
endif()

if(NOT Python3_EXECUTABLE)
  message(STATUS "WebSubInterface: Python3 not found; offline CTest scripts not registered")
  return()
endif()

set(_HUB_OFFLINE_TESTS
  hub/test_admin_access.py
  hub/test_admin_ws_ticket.py
  hub/test_conference_membership.py
  hub/test_publish_conference_filters.py
  hub/test_oauth_client_state.py
  hub/test_oidc_public_base_url.py
  hub/test_service_mode_responses.py
  hub/test_binary_publish_body_cap.py
  python_client/test_event_names.py
  python_client/test_oidc_loopback_state.py
  image_display/test_imaging_study_context.py
  image_display/test_safe_zip_extract.py
  image_display/test_livesync_subscribers.py
  )

# Working directory = WebSubInterface/ so scripts resolve Testing/Python and module paths.
set(_HUB_TEST_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")

foreach(_script ${_HUB_OFFLINE_TESTS})
  get_filename_component(_name "${_script}" NAME_WE)
  add_test(
    NAME "WebSubInterface_${_name}"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/${_script}"
    WORKING_DIRECTORY "${_HUB_TEST_ROOT}"
    )
endforeach()
