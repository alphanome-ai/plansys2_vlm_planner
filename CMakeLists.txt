cmake_minimum_required(VERSION 3.8)
project(plansys2_vlm_planner)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(plansys2_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GenerateTaskDag.srv"
  DEPENDENCIES std_msgs
)

install(DIRECTORY plansys2_vlm_planner_py/
  DESTINATION lib/python3.10/site-packages/plansys2_vlm_planner_py
  FILES_MATCHING PATTERN "*.py"
)

install(PROGRAMS
  plansys2_vlm_planner_py/vlm_planner_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME vlm_planner_node
)

install(DIRECTORY
  launch
  pddl
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY
  problems
  task_dag
  DESTINATION share/${PROJECT_NAME}
)

install(FILES
  resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
