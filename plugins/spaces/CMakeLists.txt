# Develop Spaces: three VST3 reverbs (Develop Shimmer, Develop Wash, Develop Room), a host free test
# harness, and the SDK's validator. The Steinberg VST3 SDK (MIT) stays outside the repo:
#
#   cmake -S plugins/spaces -B <build> -G "Visual Studio 17 2022" -A x64 -DVST3_SDK_ROOT=<sdk>
#   cmake --build <build> --config Release --target develop_shimmer develop_wash develop_room spaces_harness validator
# (VST3_SDK_ROOT can also come from the environment variable of that name)
cmake_minimum_required(VERSION 3.25.0)

set(VST3_SDK_ROOT "$ENV{VST3_SDK_ROOT}" CACHE PATH "Steinberg VST3 SDK root")
if(NOT EXISTS "${VST3_SDK_ROOT}/CMakeLists.txt")
    message(FATAL_ERROR "VST3_SDK_ROOT does not point at the Steinberg VST3 SDK: pass -DVST3_SDK_ROOT=<path> or set the environment variable")
endif()
set(vst3sdk_SOURCE_DIR "${VST3_SDK_ROOT}")

project(develop-spaces
    VERSION 1.0.0
    DESCRIPTION "Develop Spaces VST3 reverbs"
)

set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES OFF)
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES ON)
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF)
set(SMTG_CREATE_PLUGIN_LINK OFF)
set(SMTG_RUN_VST_VALIDATOR OFF)
set(SMTG_USE_STATIC_CRT ON)

add_subdirectory(${vst3sdk_SOURCE_DIR} ${PROJECT_BINARY_DIR}/vst3sdk)
smtg_enable_vst3_sdk()

add_library(spaces_dsp STATIC
    dsp/common.h
    dsp/fft.h
    dsp/convolver.h
    dsp/tank.h
    dsp/tank.cpp
    dsp/irsynth.h
    dsp/irsynth.cpp
)
target_compile_features(spaces_dsp PUBLIC cxx_std_17)
if(MSVC)
    target_compile_options(spaces_dsp PRIVATE /O2 /fp:precise)
endif()

set(spaces_vst_common vst/plugin_base.h vst/plugin_base.cpp)

foreach(fx shimmer wash room)
    if(fx STREQUAL "shimmer")
        set(pkg "DevelopShimmer")
    elseif(fx STREQUAL "wash")
        set(pkg "DevelopWash")
    else()
        set(pkg "DevelopRoom")
    endif()
    smtg_add_vst3plugin(develop_${fx} PACKAGE_NAME ${pkg} SOURCES_LIST ${spaces_vst_common} vst/${fx}.cpp)
    target_compile_features(develop_${fx} PUBLIC cxx_std_17)
    target_link_libraries(develop_${fx} PRIVATE sdk spaces_dsp)
    if(MSVC)
        # the SDK links Release with /DEBUG, which writes the build folder's full path into the plugin; keep only the PDB's file name
        target_link_options(develop_${fx} PRIVATE /PDBALTPATH:%_PDB%)
    endif()
endforeach()

add_executable(spaces_harness
    harness/harness.cpp
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/common/memorystream.cpp
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/hosting/module_win32.cpp
)
target_compile_features(spaces_harness PUBLIC cxx_std_17)
target_link_libraries(spaces_harness PRIVATE sdk_hosting spaces_dsp)
