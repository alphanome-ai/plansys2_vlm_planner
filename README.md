# plansys2_vlm_planner

VLM-driven planning package for CHARS that converts natural-language construction intent into:

1. A generated PDDL problem file
2. A validated symbolic plan from PlanSys2
3. A JSON task DAG published for downstream execution

## CHARS Role

This package is the Layer 3 to Layer 2 bridge in CHARS:

- Accepts high-level user intent as text.
- Uses an LLM/VLM with prompt templates to generate a PDDL problem.
- Calls PlanSys2 planner service to obtain a valid symbolic plan.
- Uses a second prompt to convert that plan into a task DAG.
- Publishes the DAG on a ROS 2 topic for allocation/execution components.

## Package Structure

```text
plansys2_vlm_planner/
  launch/
    plansys2.launch.py
    vlm_planner.launch.py
  pddl/
    domain.pddl
    problem_system_prompt.txt
    dag_system_prompt.txt
  plansys2_vlm_planner_py/
    vlm_planner_node.py
  srv/
    GenerateTaskDag.srv
  problems/      # Generated PDDL problem outputs
  task_dag/      # Generated DAG text outputs
  requirements.txt
  package.xml
  CMakeLists.txt
```

## Service API

Service type:

- `plansys2_vlm_planner/srv/GenerateTaskDag`

Request:

- `text` (string): natural-language task instruction

Response:

- `success` (bool)
- `problem_file_path` (string)
- `dag_file_path` (string)
- `message` (string)

## Runtime Topics and Services

Default endpoints from `vlm_planner_node.py` and `vlm_planner.launch.py`:

- Input service: `generate_task_dag`
- Planner service client: `/planner/get_plan` (`plansys2_msgs/srv/GetPlan`)
- DAG publish topic: `/chars/task_dag` (`std_msgs/msg/String`)

## Supported Providers

Set launch parameter `provider` to one of:

- `azure_openai`
- `openai`
- `google`

## Environment Configuration (.env)

The node requires a `.env` file and reads keys from it at startup.

Common required keys:

- `MODEL_NAME`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_KEY` (for `azure_openai`)
- `OPENAI_API_KEY` (for `openai`)
- `GEMINI_API_KEY` (for `google`)



## Dependencies

Python dependencies in `requirements.txt`:

- `langchain-core`
- `langchain-openai`
- `langchain-google-genai`

ROS dependencies in `package.xml` include:

- `rclpy`
- `std_msgs`
- `plansys2_msgs`
- `rosidl_default_runtime`

## Build

From your ROS 2 workspace root:

```bash
colcon build --packages-select plansys2_vlm_planner
source install/setup.bash
```

## Launch

### 1) Start PlanSys2 stack

```bash
ros2 launch plansys2_vlm_planner plansys2.launch.py
```

### 2) Start VLM planner node

```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py provider:=azure_openai
```

## Call the Service

```bash
ros2 service call /generate_task_dag plansys2_vlm_planner/srv/GenerateTaskDag \
  "{text: 'Assemble a 2 meter support pillar at Section A'}"
```

## End-to-End Pipeline

For each request, `vlm_planner_node` runs:

1. Generate problem text using `problem_system_prompt.txt`
2. Save timestamped problem file under `problems/`
3. Read `domain.pddl`
4. Call PlanSys2 planner service
5. Convert planner result into text summary
6. Generate DAG using `dag_system_prompt.txt`
7. Save timestamped DAG file under `task_dag/`
8. Publish DAG string to `/chars/task_dag`

## Publishing Notes

Before pushing to GitHub, review these items:

1. Replace placeholder maintainer info in `package.xml`.
2. Verify launch defaults: current launch file uses absolute paths under `/home/viswa/swarm_ws/src/...`.
3. Add `.env` and virtual environment folders to `.gitignore` if not already ignored.
4. Keep generated artifacts in `problems/` and `task_dag/` only if you want historical examples in the repo.

## License

Apache License 2.0
