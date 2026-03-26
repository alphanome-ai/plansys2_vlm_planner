# `plansys2_vlm_planner` — Technical Documentation

> **Package version:** 0.0.1  
> **Build type:** `ament_python` (Python node) + `rosidl` (custom service)  
> **License:** Apache License 2.0  
> **CHARS Layer:** 3 — Cognitive Planning  
> **ROS 2 distro target:** Humble

---

## 1. Purpose

`plansys2_vlm_planner` is the **cognitive planning entry point** of the CHARS framework. It accepts a **natural language task description** from an operator (or from the `chars_dashboard`) and runs a fully automated pipeline that produces a ready-to-execute **Task DAG JSON** for the allocator (Layer 2).

### What the pipeline does

```
Natural Language Text
        │
        ▼
[VLM Call 1] ── problem_system_prompt.txt ──► PDDL Problem file (.pddl)
        │
        ▼
[PlanSys2 Planner] ── domain.pddl + problem.pddl ──► Sequential PDDL Plan
        │
        ▼
[VLM Call 2] ── dag_system_prompt.txt ──► Task DAG JSON
        │
        ├──► Published on /chars/task_dag  (consumed by chars_central_allocator)
        └──► Saved to disk  (task_dag/ directory)
```

### Role in CHARS

| CHARS Layer | System | Interface |
|---|---|---|
| **Layer 3 (this package)** | `vlm_planner_node` | Exposes `/generate_task_dag` service; publishes to `/chars/task_dag` |
| Layer 2 | `chars_central_allocator` | Subscribes to `/chars/task_dag`; dispatches tasks to robots |
| Layer 1 | Robot action servers | Execute `pick` / `place` / `navigate` tasks from the DAG |

The operator submits a single English sentence. This node handles all translation — from language to symbols, from symbols to a validated plan, and from a plan to an executable robot task graph — automatically.

---

## 2. Package Structure

```
plansys2_vlm_planner/
├── plansys2_vlm_planner_py/
│   ├── __init__.py
│   └── vlm_planner_node.py          ← Main ROS 2 node (the full pipeline)
├── srv/
│   └── GenerateTaskDag.srv           ← Custom ROS 2 service definition
├── pddl/
│   ├── domain.pddl                   ← Static PDDL domain (robot construction world model)
│   ├── problem.pddl                  ← Example / template problem file
│   ├── problem_system_prompt.txt     ← System prompt for VLM → PDDL problem generation
│   └── dag_system_prompt.txt         ← System prompt for VLM → Task DAG generation
├── launch/
│   ├── vlm_planner.launch.py         ← Launches the vlm_planner_node with all params
│   └── plansys2.launch.py            ← Launches the PlanSys2 planner node
├── problems/                         ← Auto-created at runtime; stores generated .pddl files
├── task_dag/                         ← Auto-created at runtime; stores generated DAG .txt files
├── .env                              ← LLM API credentials (Azure/OpenAI/Google)
├── requirements.txt                  ← Python package dependencies
├── CMakeLists.txt
└── package.xml
```

---

## 3. Dependencies

### ROS 2

| Dependency | Role |
|---|---|
| `rclpy` | ROS 2 Python client |
| `std_msgs` | `std_msgs/String` for DAG topic publish |
| `plansys2_msgs` | `plansys2_msgs/srv/GetPlan` — calls the PlanSys2 planner service |
| `rosidl_default_generators` / `rosidl_default_runtime` | Generates and loads `GenerateTaskDag.srv` |

### External / Python (install via `requirements.txt` or pip)

| Package | Role |
|---|---|
| `langchain-core` | Base LangChain message types (`SystemMessage`, `HumanMessage`) |
| `langchain-openai` | `ChatOpenAI` (OpenAI API) and `AzureChatOpenAI` (Azure OpenAI) |
| `langchain-google-genai` | `ChatGoogleGenerativeAI` (Google Gemini API) |

Install before building:

```bash
pip install -r requirements.txt
# or, inside the venv/ directory that ships with the repo:
source venv/bin/activate
pip install -r requirements.txt
```

### External Services

| Service | Required by | Notes |
|---|---|---|
| **Azure OpenAI** (default) | `vlm_planner_node` | Credentials in `.env` |
| **OpenAI API** (optional) | `vlm_planner_node` | Set `provider:=openai`, `OPENAI_API_KEY` in `.env` |
| **Google Gemini** (optional) | `vlm_planner_node` | Set `provider:=google`, `GEMINI_API_KEY` in `.env` |
| **PlanSys2 planner** | `vlm_planner_node` | Must be running; called via ROS 2 service `/planner/get_plan` |

---

## 4. Custom Service: `GenerateTaskDag`

Defined in `srv/GenerateTaskDag.srv`:

```
# Request
string text          ← Natural language task description

---
# Response
bool success         ← True if the full pipeline succeeded
string problem_file_path  ← Absolute path to the saved .pddl problem file
string dag_file_path      ← Absolute path to the saved DAG .txt file
string message       ← Human-readable status or error description
```

**Service name:** `/generate_task_dag` (configurable via `service_name` parameter)

---

## 5. Node: `vlm_planner_node`

### 5.1 Overview

| Property | Value |
|---|---|
| **Node name** | `vlm_planner_node` |
| **Class** | `VLMPlannerNode` |
| **Executable** | `vlm_planner_node` |
| **Executor** | `MultiThreadedExecutor` (4 threads) |
| **Callback group** | `ReentrantCallbackGroup` — allows the service handler to block on the PlanSys2 client call without deadlocking the executor |

### 5.2 Startup Sequence

1. Loads `.env` file from one of three candidate paths (see Section 8).
2. Declares and reads all ROS parameters.
3. Creates output directories (`problems/`, `task_dag/`) if they do not exist.
4. Reads the two system prompt templates into memory.
5. Initialises the LangChain VLM client (selected by `provider` parameter).
6. Creates the DAG publisher, PlanSys2 service client, and `GenerateTaskDag` service server.

---

## 6. Topics

### Published

| Topic | Type | QoS | Description |
|---|---|---|---|
| `/chars/task_dag` | `std_msgs/String` | Default (reliable, depth 10) | The generated Task DAG serialised as a JSON string. Published once per successful pipeline execution. Consumed by `chars_central_allocator`. |

### Services Provided

| Service | Type | Description |
|---|---|---|
| `/generate_task_dag` | `plansys2_vlm_planner/srv/GenerateTaskDag` | Accepts a natural language string; runs the full 10-stage pipeline; returns success/failure and file paths. |

### Services Called

| Service | Type | Description |
|---|---|---|
| `/planner/get_plan` | `plansys2_msgs/srv/GetPlan` | Calls the PlanSys2 Fast Downward planner. Sends the static domain text + VLM-generated problem text; receives a timed `Plan` message. |

---

## 7. Parameters

All parameters are declared in the node and exposed as launch arguments in `vlm_planner.launch.py`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `provider` | `string` | `"azure_openai"` | VLM provider to use. One of: `"openai"`, `"azure_openai"`, `"google"` |
| `problem_system_prompt_path` | `string` | `<ws>/pddl/problem_system_prompt.txt` | Absolute path to the system prompt for PDDL problem generation. This file contains the full domain, generation rules, step-by-step reasoning instructions, and worked examples for the LLM. |
| `dag_system_prompt_path` | `string` | `<ws>/pddl/dag_system_prompt.txt` | Absolute path to the system prompt for DAG generation. Contains coordinate decoding rules, task construction rules, dependency identification rules, and reference examples. |
| `domain_file_path` | `string` | `<ws>/pddl/domain.pddl` | Absolute path to the static PDDL domain file passed to PlanSys2. |
| `problem_output_dir` | `string` | `<ws>/problems` | Directory where generated PDDL problem files are saved (timestamped filenames). Auto-created if missing. |
| `dag_output_dir` | `string` | `<ws>/task_dag` | Directory where generated DAG JSON files are saved (timestamped filenames). Auto-created if missing. |
| `planner_service_name` | `string` | `"/planner/get_plan"` | Full ROS 2 service name of the PlanSys2 planner. |
| `planner_timeout_sec` | `double` | `60.0` | Maximum seconds to wait for the PlanSys2 planner to return a plan. A `TimeoutError` is raised and the pipeline fails if exceeded. |
| `service_name` | `string` | `"generate_task_dag"` | The name under which the `GenerateTaskDag` service is advertised. |
| `dag_topic` | `string` | `"/chars/task_dag"` | The topic on which the final DAG JSON string is published. |

---

## 8. Environment Variables (`.env` file)

The node loads a `.env` file at startup. It searches these paths in order, using the first one found:

1. `/home/viswa/swarm_ws/src/plansys2_vlm_planner/.env`
2. `<current working directory>/.env`
3. `<package root>/.env`

Required variables depend on the `provider` parameter:

### Azure OpenAI (default `provider=azure_openai`)

| Variable | Description |
|---|---|
| `MODEL_NAME` | Deployment model name (e.g. `gpt-5.2`) |
| `AZURE_OPENAI_ENDPOINT` | Azure Cognitive Services endpoint URL |
| `AZURE_OPENAI_API_VERSION` | API version string (e.g. `2025-04-01-preview`) |
| `AZURE_OPENAI_DEPLOYMENT` | Azure deployment name |
| `AZURE_OPENAI_API_KEY` | Azure API key |

### OpenAI (`provider=openai`)

| Variable | Description |
|---|---|
| `MODEL_NAME` | Model name (e.g. `gpt-4o`) |
| `OPENAI_API_KEY` | OpenAI secret key |

### Google Gemini (`provider=google`)

| Variable | Description |
|---|---|
| `MODEL_NAME` | Model name (e.g. `gemini-1.5-pro`) |
| `GEMINI_API_KEY` | Google AI Studio / Vertex AI key |

> **⚠️ Security note:** The `.env` file ships with a real API key in the repository. Before publishing or sharing this repo, rotate the `AZURE_OPENAI_API_KEY` value and add `.env` to `.gitignore`.

---

## 9. The 10-Stage Pipeline

When the `/generate_task_dag` service is called, the node executes this pipeline sequentially. Each stage is logged with its stage number.

| Stage | Description | Output |
|---|---|---|
| **1** | Parse and validate the incoming text input. Reject if empty. | Validated `text_input` string |
| **2** | Compose a user task prompt: `"Generate a PDDL problem file for: {text_input}"`. Call VLM with `problem_system_prompt` as system. | Raw PDDL problem text string |
| **3** | Save generated PDDL to `problem_output_dir/problem_<timestamp>.pddl` | `.pddl` file on disk |
| **4** | Load the static `domain.pddl` file from disk | Domain text string |
| **5** | Call `GetPlan` service with domain + problem text. Block until result or timeout. | `plansys2_msgs/Plan` message |
| **6** | Convert plan items to human-readable text: `time=X, duration=Y, action=Z` (one line per action) | Plan text string |
| **7** | Compose DAG user task: `"Based on instruction: {text} and plan: {plan_text}, generate the Task DAG."` | DAG user prompt |
| **8** | Call VLM with `dag_system_prompt` as system and DAG user prompt. | Raw DAG JSON string |
| **9** | Save generated DAG to `dag_output_dir/task_dag_<timestamp>.txt` | `.txt` file on disk |
| **10** | Publish DAG JSON string on `dag_topic` as `std_msgs/String` | Message on `/chars/task_dag` |

On any stage failure (VLM error, planner timeout, empty response), the pipeline short-circuits and returns `success=false` with the error description in `message`.

### VLM Configuration

Both VLM calls use:
- **Temperature:** `0.2` — low for deterministic, structured output (PDDL and JSON)
- **Max tokens:** `8192` (OpenAI / Azure) or `32768` (Google Gemini)

---

## 10. PDDL Domain (`pddl/domain.pddl`)

The domain `single_robot_construction_xyz` models a construction task where a robot picks ArUco-tagged boxes from a pickup zone and places them at 3D target coordinates.

### Types

| Type | Description |
|---|---|
| `robot` | The mobile manipulator agent |
| `box` | An ArUco-tagged construction box |
| `location` | 2D navigation waypoint |
| `x_coord`, `y_coord`, `z_coord` | Symbolic 3D coordinate tokens |

### Predicates (key)

| Predicate | Meaning |
|---|---|
| `robot_at ?r ?l` | Robot `r` is at location `l` |
| `hand_empty ?r` | Robot `r` is not holding anything |
| `holding ?r ?b` | Robot `r` is holding box `b` |
| `box_in_pickup_zone ?b ?l` | Box `b` is in the pickup zone at location `l` |
| `box_at_xyz ?b ?x ?y ?z` | Box `b` has been placed at coordinate (x, y, z) |
| `xyz_free ?x ?y ?z` | The placement slot at (x, y, z) is empty |
| `is_ground_level ?z` | Z coordinate is ground level |
| `z_above ?z_top ?z_below` | Stacking relationship (z_top is one level above z_below) |

### Durative Actions

| Action | Duration | Description |
|---|---|---|
| `move` | 10s | Navigate from one location to another. **Filtered out of generated DAGs** — handled autonomously by Nav2. |
| `pick` | 5s | Pick up a box from the pickup zone. Robot must be at the pickup location. |
| `place_ground` | 5s | Place a box directly on the floor at a coordinate slot. Slot must be free and at ground level. |
| `place_stacked` | 5s | Place a box on top of another already-placed box. Uses `z_above` stacking relationship. |

### Coordinate Encoding Convention

PDDL tokens are symbolic names (not numbers). The VLM encodes real-world float coordinates into token names using a reversible convention:

| Token | Real Value | Rule |
|---|---|---|
| `x_0p5` | 0.5 m | `p` = decimal point |
| `x_neg1p0` | -1.0 m | `neg` = negative |
| `y_0p0` | 0.0 m | |
| `z0` | 0.22 m | ground level |
| `z20` | 0.42 m | 1 box high (0.22 + 1×0.20) |
| `z40` | 0.62 m | 2 boxes high |
| `z60` | 0.82 m | 3 boxes high |

The DAG prompt instructs the second VLM call to **decode** these tokens back to real floats before writing the pose fields.

---

## 11. System Prompts

### `problem_system_prompt.txt` (PDDL Problem Generator)

Instructs the LLM to act as an expert PDDL problem generator. Contains:

- The full domain PDDL (embedded in the prompt) for reference.
- **7 generation rules** covering: object instantiation, coordinate naming, location definitions, physics constraints, initial state, goal specification, and output format.
- **Step-by-step reasoning process** guiding the LLM to parse the request, build objects, build `:init`, and build `:goal` before writing any PDDL.
- **Two worked examples:** single box placement and two-box stacking.
- **Output constraint:** Raw PDDL only — no markdown, no explanations.

### `dag_system_prompt.txt` (Task DAG Generator)

Instructs the LLM to act as a robotic task compiler. Contains:

- **Step 1:** Filter rules — discard `move` actions, keep only `pick`, `place_ground`, `place_stacked`.
- **Step 2:** Coordinate decoding rules — convert PDDL token names back to float values.
- **Step 3:** Task construction rules — how to build `pick` and `place` task objects with correct `task_id`, `task_type`, `frame_id`, `pose`, and `dependencies`.
- **Step 4:** Dependency identification — handling `place_ground` (no prior deps) vs `place_stacked` (depends on base box being placed first).
- **Step 5:** Output ordering — topological sort requirement.
- **Two reference examples:** single box placement, two-box stacking with dependency chain.
- **Output constraint:** Raw JSON only — must begin with `{` and end with `}`.

---

## 12. Generated DAG JSON Schema

The published `std_msgs/String` on `/chars/task_dag` contains a JSON object matching this schema:

```json
{
  "tasks": [
    {
      "task_id": "pick_box_28",
      "task_type": "pick",
      "frame_id": "aruco_box_28",
      "pose": {},
      "dependencies": []
    },
    {
      "task_id": "place_box_28",
      "task_type": "place",
      "frame_id": "map",
      "pose": {"x": 0.5, "y": 0.5, "z": 0.22},
      "dependencies": ["pick_box_28"],
      "constraints": {"same_agent_as": "pick_box_28"}
    }
  ]
}
```

| Field | `pick` task | `place` task |
|---|---|---|
| `task_id` | `"pick_box_NN"` | `"place_box_NN"` |
| `task_type` | `"pick"` | `"place"` |
| `frame_id` | `"aruco_box_NN"` — TF frame of the box's ArUco marker | `"map"` |
| `pose` | `{}` — empty (position from TF at execution time) | `{"x": float, "y": float, "z": float}` |
| `dependencies` | `[]` (ground) or `["place_box_NN"]` (stacked) | `["pick_box_NN"]` |
| `constraints` | *(omitted)* | `{"same_agent_as": "pick_box_NN"}` |

---

## 13. Building the Package

```bash
cd ~/swarm_ws

# Install Python dependencies first
pip install langchain-core langchain-openai langchain-google-genai
# or: source venv/bin/activate (if using the bundled venv)

# Build
colcon build --packages-select plansys2_vlm_planner

# Source
source install/setup.bash
```

---

## 14. Launching

### Step 1 — Start PlanSys2 (required first)

PlanSys2 provides the `/planner/get_plan` service. Launch it with the CHARS domain:

```bash
ros2 launch plansys2_vlm_planner plansys2.launch.py
```

This starts the `plansys2_node` from `plansys2_bringup`, pre-loaded with the CHARS PDDL domain (`pddl/domain.pddl`).

| Launch Argument | Default | Description |
|---|---|---|
| `model_file` | `pddl/domain.pddl` | PDDL domain file for PlanSys2 |
| `namespace` | `""` | Optional ROS namespace for PlanSys2 nodes |
| `params_file` | `plansys2_bringup` default | PlanSys2 node parameters YAML |
| `default_action_bt_xml_filename` | `plansys2_executor` default | BT XML for action execution |

---

### Step 2 — Start the VLM Planner Node

```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py
```

**With Azure OpenAI (default):**
```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py \
  provider:=azure_openai
```

**With OpenAI:**
```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py \
  provider:=openai
```

**With Google Gemini:**
```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py \
  provider:=google
```

**Custom prompt paths (e.g., after editing prompts):**
```bash
ros2 launch plansys2_vlm_planner vlm_planner.launch.py \
  provider:=azure_openai \
  problem_system_prompt_path:=/path/to/custom_problem_prompt.txt \
  dag_system_prompt_path:=/path/to/custom_dag_prompt.txt
```

All launch arguments mirror the node parameters from Section 7.

---

## 15. Calling the Service

### From the `chars_dashboard`

Click **"+ Submit Text Input"** in the dashboard, type the instruction, and click **Submit Text →**. The dashboard calls `/generate_task_dag` directly via roslib JS.

### From the CLI

```bash
ros2 service call /generate_task_dag \
  plansys2_vlm_planner/srv/GenerateTaskDag \
  "{text: 'Pick up box 28 and place it at (0.5, 0.5, 0.22)'}"
```

Expected response on success:

```yaml
success: true
problem_file_path: '/home/viswa/swarm_ws/src/plansys2_vlm_planner/problems/problem_20260326_104500.pddl'
dag_file_path: '/home/viswa/swarm_ws/src/plansys2_vlm_planner/task_dag/task_dag_20260326_104502.txt'
message: 'Pipeline executed successfully'
```

### Monitor the DAG output

```bash
ros2 topic echo /chars/task_dag
```

---

## 16. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `FileNotFoundError: No .env file found` | `.env` not in any of the 3 search paths | Copy `.env` to the workspace source directory: `cp .env ~/swarm_ws/src/plansys2_vlm_planner/.env` |
| `Required environment variable missing in .env: MODEL_NAME` | `.env` is missing a required key | Ensure all 5 Azure keys (or appropriate keys for your provider) are present in `.env` |
| `Planner service not ready: /planner/get_plan` | PlanSys2 not running or different namespace | Run `plansys2.launch.py` first; check with `ros2 service list \| grep get_plan` |
| `TimeoutError: Timed out waiting for planner response` | PlanSys2 solver taking too long or plan infeasible | Increase `planner_timeout_sec`; simplify the task; verify the problem is solvable |
| `Planner failed to generate a plan` | PDDL problem file has syntax errors or is inconsistent with domain | Check the saved `.pddl` file in `problems/`; validate with an offline PDDL validator |
| `VLM returned empty problem text` or `empty DAG text` | LLM returned an empty or malformed response | Check API key validity; increase `max_tokens` if content is being truncated; review prompt files |
| DAG published but allocator ignores it | Allocator resets on repeated publishes or QoS mismatch | Ensure the allocator's subscriber QoS matches the publisher (reliable, depth 10); see `chars_central_allocator` docs |
| `No module named 'langchain_openai'` | Python dependencies not installed | Run `pip install -r requirements.txt` in the active Python environment before building |
| Wrong coordinates in DAG (all 0.0) | DAG prompt did not decode PDDL tokens correctly | Check `dag_system_prompt.txt` coordinate decoding rules; verify the plan text includes the correct token names |

---

## 17. Integration Notes for CHARS

- **Always start PlanSys2 before the VLM planner node.** The node validates planner availability on each service call (5 s timeout), but it does not wait at startup.
- The pipeline is **synchronous and blocking** per request — only one planning request can run at a time. The `ReentrantCallbackGroup` prevents a second service call from interfering but it will queue behind the first.
- **Output files are permanent.** The `problems/` and `task_dag/` directories accumulate files across sessions. Periodically clean them or configure `problem_output_dir` / `dag_output_dir` to a temporary location.
- The **same domain.pddl is used for all requests.** To change the robot's capabilities (e.g., add a new action type), edit `domain.pddl` and update both system prompts to reflect the change.
- The `constraints: {"same_agent_as": "pick_box_NN"}` field in `place` tasks is a hint to the allocator that the same physical robot should perform both the pick and the place for a given box. This prevents a box from being handed off between robots mid-task, which the current hardware cannot support.
- The `.env` file's `AZURE_OPENAI_API_KEY` must be rotated periodically per Azure policy. When rotating, update the file in the workspace source directory and restart the node.
