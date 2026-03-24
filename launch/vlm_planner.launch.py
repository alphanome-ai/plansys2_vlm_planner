#!/usr/bin/env python3
"""Launch file for plansys2_vlm_planner pipeline node."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    provider_arg = DeclareLaunchArgument(
        "provider",
        default_value="azure_openai",
        description="VLM provider: google, openai, or azure_openai",
    )
    problem_prompt_arg = DeclareLaunchArgument(
        "problem_system_prompt_path",
        default_value="/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/problem_system_prompt.txt",
        description="Problem generation prompt path",
    )
    dag_prompt_arg = DeclareLaunchArgument(
        "dag_system_prompt_path",
        default_value="/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/dag_system_prompt.txt",
        description="DAG generation prompt path",
    )
    domain_file_arg = DeclareLaunchArgument(
        "domain_file_path",
        default_value="/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/domain.pddl",
        description="Predefined PDDL domain file path",
    )
    problem_output_arg = DeclareLaunchArgument(
        "problem_output_dir",
        default_value="/home/viswa/swarm_ws/src/plansys2_vlm_planner/problems",
        description="Directory for generated PDDL problems",
    )
    dag_output_arg = DeclareLaunchArgument(
        "dag_output_dir",
        default_value="/home/viswa/swarm_ws/src/plansys2_vlm_planner/task_dag",
        description="Directory for generated DAG files",
    )
    planner_service_arg = DeclareLaunchArgument(
        "planner_service_name",
        default_value="/planner/get_plan",
        description="Planner service endpoint",
    )
    planner_timeout_arg = DeclareLaunchArgument(
        "planner_timeout_sec",
        default_value="60.0",
        description="Planner request timeout in seconds",
    )
    service_name_arg = DeclareLaunchArgument(
        "service_name",
        default_value="generate_task_dag",
        description="Input service name for text requests",
    )
    dag_topic_arg = DeclareLaunchArgument(
        "dag_topic",
        default_value="/chars/task_dag",
        description="Topic to publish generated DAG",
    )

    node = Node(
        package="plansys2_vlm_planner",
        executable="vlm_planner_node",
        name="vlm_planner_node",
        output="screen",
        parameters=[
            {
                "provider": LaunchConfiguration("provider"),
                "problem_system_prompt_path": LaunchConfiguration("problem_system_prompt_path"),
                "dag_system_prompt_path": LaunchConfiguration("dag_system_prompt_path"),
                "domain_file_path": LaunchConfiguration("domain_file_path"),
                "problem_output_dir": LaunchConfiguration("problem_output_dir"),
                "dag_output_dir": LaunchConfiguration("dag_output_dir"),
                "planner_service_name": LaunchConfiguration("planner_service_name"),
                "planner_timeout_sec": LaunchConfiguration("planner_timeout_sec"),
                "service_name": LaunchConfiguration("service_name"),
                "dag_topic": LaunchConfiguration("dag_topic"),
            }
        ],
        emulate_tty=True,
    )

    return LaunchDescription(
        [
            provider_arg,
            problem_prompt_arg,
            dag_prompt_arg,
            domain_file_arg,
            problem_output_arg,
            dag_output_arg,
            planner_service_arg,
            planner_timeout_arg,
            service_name_arg,
            dag_topic_arg,
            node,
        ]
    )
