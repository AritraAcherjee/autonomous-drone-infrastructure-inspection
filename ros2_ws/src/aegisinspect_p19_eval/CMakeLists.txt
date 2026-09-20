cmake_minimum_required(VERSION 3.22.1)
project(aegisinspect_p19_eval)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(gz-sim 10 REQUIRED)
find_package(gz-plugin 4 REQUIRED COMPONENTS register)
find_package(gz-transport 15 REQUIRED)
find_package(gz-msgs 12 REQUIRED)

ament_python_install_package(${PROJECT_NAME})

add_library(p19_update_attestor SHARED src/update_attestor.cpp)
target_compile_features(p19_update_attestor PUBLIC cxx_std_17)
target_link_libraries(p19_update_attestor PRIVATE
  gz-sim::gz-sim gz-plugin::register gz-transport::gz-transport gz-msgs::gz-msgs)

install(TARGETS p19_update_attestor LIBRARY DESTINATION lib)
install(PROGRAMS scripts/readiness_node.py DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config launch models worlds assets DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(p19_eval_contracts test/test_contracts.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
  ament_add_pytest_test(p19_eval_static test/test_static_contracts.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR} TIMEOUT 60)
endif()

ament_package()
