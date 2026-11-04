# Develop Character VST3 plugins: Develop Tape, Develop Lo-fi, Develop Transient, the charhost test harness and the
# SDK's validator. The Steinberg VST3 SDK (MIT) stays outside the repo; point VST3_SDK_ROOT at it (-D or the
# environment variable of that name).
#
#   cmake -S plugins/character -B plugins/character/build -G "Visual Studio 17 2022" -A x64 -DVST3_SDK_ROOT=<sdk>
#   cmake --build plugins/character/build --config Release
cmake_minimum_required(VERSION 3.25.0)

set(VST3_SDK_ROOT "$ENV{VST3_SDK_ROOT}" CACHE PATH "Steinberg VST3 SDK root")
if(NOT EXISTS "${VST3_SDK_ROOT}/CMakeLists.txt")
    message(FATAL_ERROR "VST3_SDK_ROOT does not point at the Steinberg VST3 SDK: pass -DVST3_SDK_ROOT=<path> or set the environment variable")
endif()
set(vst3sdk_SOURCE_DIR "${VST3_SDK_ROOT}")

option(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES "" OFF)
option(SMTG_ENABLE_VST3_HOSTING_EXAMPLES "" ON)
option(SMTG_ENABLE_VSTGUI_SUPPORT "" OFF)
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)
set(SMTG_RUN_VST_VALIDATOR OFF CACHE BOOL "" FORCE)
# no Visual C++ runtime needed on the user's machine, as in plugins/spaces
set(SMTG_USE_STATIC_CRT ON CACHE BOOL "" FORCE)

project(develop-character VERSION 1.0.0 LANGUAGES CXX)

add_subdirectory(${vst3sdk_SOURCE_DIR} ${PROJECT_BINARY_DIR}/vst3sdk)
smtg_enable_vst3_sdk()

set(DSP_HEADERS
    dsp/common.h dsp/params.h dsp/output_stage.h dsp/tape_parts.h dsp/tape_engine.h dsp/ja_gain_table.h
    dsp/lofi_parts.h dsp/lofi_engine.h dsp/noise_follow.h dsp/transient_engine.h vst/devplugin.h)

function(develop_plugin target name source)
    smtg_add_vst3plugin(${target} PACKAGE_NAME ${name} SOURCES_LIST ${source} ${DSP_HEADERS})
    target_compile_features(${target} PUBLIC cxx_std_17)
    target_link_libraries(${target} PRIVATE sdk)
    if(MSVC)
        target_compile_options(${target} PRIVATE /O2 /fp:precise /W3)
        # the SDK links Release with /DEBUG, which writes the build folder's full path into the plugin; keep only the PDB's file name
        target_link_options(${target} PRIVATE /PDBALTPATH:%_PDB%)
    endif()
endfunction()

develop_plugin(develop_tape DevelopTape vst/tape_entry.cpp)
develop_plugin(develop_lofi DevelopLofi vst/lofi_entry.cpp)
develop_plugin(develop_transient DevelopTransient vst/transient_entry.cpp)

add_executable(charhost harness/charhost.cpp harness/wav.h ${DSP_HEADERS}
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/hosting/module_win32.cpp)
target_compile_features(charhost PUBLIC cxx_std_17)
target_link_libraries(charhost PRIVATE sdk_hosting sdk_common base pluginterfaces)
if(MSVC)
    target_compile_options(charhost PRIVATE /O2 /fp:precise /W3)
endif()
