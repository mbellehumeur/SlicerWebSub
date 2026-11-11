cmake_minimum_required(VERSION 3.20.6...3.22.6 FATAL_ERROR)

project(WebSubInterface)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://bellehumeur-engineering.com/worklist-client")
set(EXTENSION_CATEGORY "Informatics")
set(EXTENSION_CONTRIBUTORS "Martin Bellehumeur")
set(EXTENSION_DESCRIPTION "WebSub messaging infrastructure that connects users of image displays, worklists, reporting tools, conferencing tools, remote inference models and AI Orchestrators.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/WebSub_Server_logo.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/banner.png https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/hub-admin.png https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/worklist-client.png https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/Screenshot-SlicerHubQt.png https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/Screenshot-classroom.png https://raw.githubusercontent.com/mbellehumeur/SlicerWebSub/main/WebSubInterface/docs/images/Screenshot-evidence-creators.png https://img.youtube.com/vi/ENyYdJ_fHYI/hqdefault.jpg https://img.youtube.com/vi/vNtK8ldMcw0/hqdefault.jpg")
set(EXTENSION_DEPENDS "NA")

#-----------------------------------------------------------------------------
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
add_subdirectory(WebSubInterface)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
