cmake_minimum_required(VERSION 3.22.1)
project(aegisinspect_p19_eval)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(gz-sim 10 REQUIRED)
find_package(gz-plugin 4 REQUIRED COMPONENTS register)
find_package(gz-transport 15 REQUIRED)
find_package(gz-msgs 12 REQUIRED)
find_package(OpenSSL REQUIRED)

ament_python_install_package(${PROJECT_NAME})

add_library(p19_sensor_batch_certificate SHARED src/sensor_batch_certificate.cpp)
target_compile_features(p19_sensor_batch_certificate PUBLIC cxx_std_17)
target_include_directories(p19_sensor_batch_certificate PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(p19_sensor_batch_certificate PRIVATE
  gz-transport::gz-transport gz-msgs::gz-msgs OpenSSL::Crypto)

add_library(p19_update_attestor SHARED src/update_attestor.cpp)
target_compile_features(p19_update_attestor PUBLIC cxx_std_17)
target_include_directories(p19_update_attestor PRIVATE include)
target_link_libraries(p19_update_attestor PRIVATE
  p19_sensor_batch_certificate gz-sim::gz-sim gz-plugin::register
  gz-transport::gz-transport gz-msgs::gz-msgs)

add_library(p19_batch_scene_configurator SHARED src/batch_scene_configurator.cpp)
target_compile_features(p19_batch_scene_configurator PUBLIC cxx_std_17)
target_include_directories(p19_batch_scene_configurator PRIVATE include)
target_link_libraries(p19_batch_scene_configurator PRIVATE
  p19_sensor_batch_certificate gz-sim::gz-sim gz-plugin::register)

install(TARGETS p19_sensor_batch_certificate p19_update_attestor
  p19_batch_scene_configurator
  LIBRARY DESTINATION lib)
install(DIRECTORY include/ DESTINATION include)
install(PROGRAMS scripts/readiness_node.py DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config launch models worlds assets gazebo_patch
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(p19_eval_contracts test/test_contracts.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_eval_static test/test_static_contracts.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_harness_lifecycle test/test_harness_lifecycle.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_sensor_batch_certificate
    test/test_sensor_batch_certificate.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_evidence_interfaces
    test/test_evidence_interfaces.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_diagnostic_observability
    test/test_diagnostic_observability.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
endif()

ament_package()
