#!/usr/bin/env python3
"""
VLM Planner Node

Pipeline per request:
1) Accept text input via service
2) Inject text into problem prompt template and call VLM
3) Save generated PDDL problem file
4) Call PlanSys2 planner with predefined domain + generated problem
5) Inject text + plan into DAG prompt template and call VLM
6) Save DAG and publish it on a predefined topic
"""

import os
import threading
import traceback
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from std_msgs.msg import String
from plansys2_msgs.srv import GetPlan

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)

from plansys2_vlm_planner.srv import GenerateTaskDag


class VLMPlannerNode(Node):
    """Service node that runs VLM->PlanSys2->VLM and publishes DAG."""

    def __init__(self):
        super().__init__("vlm_planner_node")

        self._load_env_file()

        self.declare_parameter("provider", "")
        self.declare_parameter(
            "problem_system_prompt_path",
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/problem_system_prompt.txt",
        )
        self.declare_parameter(
            "dag_system_prompt_path",
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/dag_system_prompt.txt",
        )
        self.declare_parameter(
            "domain_file_path",
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/pddl/domain.pddl",
        )
        self.declare_parameter(
            "problem_output_dir",
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/problems",
        )
        self.declare_parameter(
            "dag_output_dir",
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/task_dag",
        )
        self.declare_parameter("planner_service_name", "/planner/get_plan")
        self.declare_parameter("planner_timeout_sec", 60.0)
        self.declare_parameter("service_name", "generate_task_dag")
        self.declare_parameter("dag_topic", "/chars/task_dag")

        self.provider = str(self.get_parameter("provider").value)
        self.model_name = self._get_required_env("MODEL_NAME")
        self.azure_endpoint = self._get_required_env("AZURE_OPENAI_ENDPOINT")
        self.azure_api_version = self._get_required_env("AZURE_OPENAI_API_VERSION")
        self.azure_deployment = self._get_required_env("AZURE_OPENAI_DEPLOYMENT")
        self.problem_system_prompt_path = str(
            self.get_parameter("problem_system_prompt_path").value
        )
        self.dag_system_prompt_path = str(
            self.get_parameter("dag_system_prompt_path").value
        )
        self.domain_file_path = str(self.get_parameter("domain_file_path").value)
        self.problem_output_dir = str(self.get_parameter("problem_output_dir").value)
        self.dag_output_dir = str(self.get_parameter("dag_output_dir").value)
        self.planner_service_name = str(self.get_parameter("planner_service_name").value)
        self.planner_timeout_sec = float(self.get_parameter("planner_timeout_sec").value)
        self.service_name = str(self.get_parameter("service_name").value)
        self.dag_topic = str(self.get_parameter("dag_topic").value)

        Path(self.problem_output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.dag_output_dir).mkdir(parents=True, exist_ok=True)

        self.problem_prompt_template = self._read_required_file(
            self.problem_system_prompt_path,
            "problem system prompt",
        )
        self.dag_prompt_template = self._read_required_file(
            self.dag_system_prompt_path,
            "DAG system prompt",
        )

        self.callback_group = ReentrantCallbackGroup()

        self.dag_publisher = self.create_publisher(String, self.dag_topic, 10)
        self.plan_client = self.create_client(
            GetPlan,
            self.planner_service_name,
            callback_group=self.callback_group,
        )
        self.service = self.create_service(
            GenerateTaskDag,
            self.service_name,
            self._handle_request,
            callback_group=self.callback_group,
        )

        self.vlm = self._initialize_vlm()

        self.get_logger().info(
            "VLM planner node ready | provider=%s model=%s service=%s dag_topic=%s"
            % (self.provider, self.model_name, self.service_name, self.dag_topic)
        )

    def _load_env_file(self):
        """Load key-value pairs from .env into process environment."""
        env_candidates = [
            "/home/viswa/swarm_ws/src/plansys2_vlm_planner/.env",
            os.path.join(os.getcwd(), ".env"),
            os.path.join(str(Path(__file__).resolve().parent.parent), ".env"),
        ]

        env_path = None
        for candidate in env_candidates:
            if os.path.exists(candidate):
                env_path = candidate
                break

        if env_path is None:
            raise FileNotFoundError(
                "No .env file found. Expected one of: " + ", ".join(env_candidates)
            )

        with open(env_path, "r", encoding="utf-8") as file_handle:
            for raw_line in file_handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

    def _get_required_env(self, name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise ValueError(f"Required environment variable missing in .env: {name}")
        return value

    def _read_required_file(self, path: str, label: str) -> str:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{label} file not found: {path}")
        with open(path, "r", encoding="utf-8") as file_handle:
            return file_handle.read()

    def _initialize_vlm(self):
        provider = self.provider.lower()
        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return ChatOpenAI(
                model=self.model_name,
                api_key=api_key,
                temperature=0.2,
                max_tokens=8192,
            )

        if provider == "azure_openai":
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")

            azure_endpoint = self.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
            if not azure_endpoint:
                raise ValueError(
                    "Azure endpoint missing. Set parameter 'azure_endpoint' or AZURE_OPENAI_ENDPOINT"
                )

            api_version = self.azure_api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "")
            if not api_version:
                raise ValueError(
                    "Azure API version missing. Set parameter 'azure_api_version' or AZURE_OPENAI_API_VERSION"
                )

            deployment = self.azure_deployment or self.model_name
            if not deployment:
                raise ValueError(
                    "Azure deployment missing. Set parameter 'azure_deployment' or 'model_name'"
                )

            self.get_logger().info(
                f"Azure OpenAI endpoint: {azure_endpoint}"
            )
            self.get_logger().info(
                f"Azure OpenAI API version: {api_version}"
            )
            self.get_logger().info(
                f"Azure OpenAI deployment: {deployment}"
            )
            self.get_logger().info("Azure OpenAI API key loaded from .env")

            return AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=api_version,
                azure_deployment=deployment,
                temperature=0.2,
                max_tokens=8192,
            )

        if provider == "google":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")

            safety_settings = {
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=0.2,
                max_tokens=32768,
                safety_settings=safety_settings,
            )

        raise ValueError(f"Unsupported provider: {self.provider}")


    def _extract_text(self, model_result) -> str:
        if not hasattr(model_result, "content"):
            return str(model_result)

        content = model_result.content
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            fragments = []
            for item in content:
                if isinstance(item, str):
                    fragments.append(item)
                elif isinstance(item, dict) and "text" in item:
                    fragments.append(str(item["text"]))
                else:
                    fragments.append(str(item))
            return "\n".join(fragments)

        return str(content)

    def _invoke_vlm(self, system_rules: str, user_task: str) -> str:
        messages = [
            SystemMessage(content=system_rules),
            HumanMessage(content=user_task),
        ]
        result = self.vlm.invoke(messages)
        return self._extract_text(result)

    def _save_text(self, output_dir: str, prefix: str, suffix: str, content: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"{prefix}_{timestamp}.{suffix}")
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
        return file_path

    def _wait_for_planner(self) -> None:
        if self.plan_client.service_is_ready():
            return

        if not self.plan_client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(
                f"Planner service not ready: {self.planner_service_name}"
            )

    def _call_planner(self, domain_text: str, problem_text: str):
        self._wait_for_planner()

        request = GetPlan.Request()
        request.domain = domain_text
        request.problem = problem_text

        future = self.plan_client.call_async(request)
        done_event = threading.Event()
        future.add_done_callback(lambda _: done_event.set())

        if not done_event.wait(timeout=self.planner_timeout_sec):
            raise TimeoutError("Timed out waiting for planner response")

        result = future.result()
        if result is None:
            raise RuntimeError("Planner returned no response")
        if not result.success:
            raise RuntimeError("Planner failed to generate a plan")

        return result.plan

    def _plan_to_text(self, plan_msg) -> str:
        lines = []
        for item in plan_msg.items:
            action = str(item.action)
            time_value = float(item.time)
            duration = float(item.duration)
            lines.append(f"time={time_value:.3f}, duration={duration:.3f}, action={action}")
        return "\n".join(lines)

    def _handle_request(self, request, response):
        text_input = request.text.strip()
        self.get_logger().info("Received generate_task_dag request")
        if not text_input:
            self.get_logger().warn("Request rejected: input text is empty")
            response.success = False
            response.problem_file_path = ""
            response.dag_file_path = ""
            response.message = "Input text is empty"
            return response

        try:
            self.get_logger().info("Stage 1/10: preparing problem-generation task")
            problem_user_task = (
                f"Generate a PDDL problem file for the following instruction:\n{text_input}"
            )

            self.get_logger().info("Stage 2/10: invoking VLM for PDDL problem generation")
            problem_text = self._invoke_vlm(
                self.problem_prompt_template, problem_user_task
            ).strip()
            self.get_logger().info("Stage 2/10 complete: received problem text from VLM")
            if not problem_text:
                raise RuntimeError("VLM returned empty problem text")

            self.get_logger().info("Stage 3/10: saving generated problem file")
            problem_file_path = self._save_text(
                self.problem_output_dir,
                "problem",
                "pddl",
                problem_text,
            )
            self.get_logger().info(f"Stage 3/10 complete: problem saved at {problem_file_path}")

            self.get_logger().info("Stage 4/10: loading predefined domain file")
            domain_text = self._read_required_file(self.domain_file_path, "domain")
            self.get_logger().info("Stage 4/10 complete: domain file loaded")

            self.get_logger().info("Stage 5/10: requesting plan from planner service")
            plan_msg = self._call_planner(domain_text, problem_text)
            self.get_logger().info(
                f"Stage 5/10 complete: planner returned {len(plan_msg.items)} plan items"
            )

            self.get_logger().info("Stage 6/10: converting planner result to text")
            plan_text = self._plan_to_text(plan_msg)
            self.get_logger().info("Stage 6/10 complete: plan text prepared")

            self.get_logger().info("Stage 7/10: preparing DAG-generation task")
            dag_user_task = (
                f"Based on the following user instruction:\n{text_input}\n\n"
                f"And this generated plan:\n{plan_text}\n\n"
                "Generate the requested Task DAG."
            )

            self.get_logger().info("Stage 8/10: invoking VLM for DAG generation")
            dag_text = self._invoke_vlm(
                self.dag_prompt_template, dag_user_task
            ).strip()
            self.get_logger().info("Stage 8/10 complete: received DAG text from VLM")
            if not dag_text:
                raise RuntimeError("VLM returned empty DAG text")

            self.get_logger().info("Stage 9/10: saving generated DAG file")
            dag_file_path = self._save_text(
                self.dag_output_dir,
                "task_dag",
                "txt",
                dag_text,
            )
            self.get_logger().info(f"Stage 9/10 complete: DAG saved at {dag_file_path}")

            self.get_logger().info("Stage 10/10: publishing DAG to topic")
            dag_msg = String()
            dag_msg.data = dag_text
            self.dag_publisher.publish(dag_msg)
            self.get_logger().info(f"Stage 10/10 complete: DAG published on {self.dag_topic}")

            response.success = True
            response.problem_file_path = problem_file_path
            response.dag_file_path = dag_file_path
            response.message = "Pipeline executed successfully"
            self.get_logger().info("Pipeline completed successfully")

        except Exception as exc:
            response.success = False
            response.problem_file_path = ""
            response.dag_file_path = ""
            response.message = f"Pipeline failed: {exc}"
            self.get_logger().error(response.message)
            self.get_logger().error(traceback.format_exc())

        return response


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = None

    try:
        node = VLMPlannerNode()
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"VLM planner node failed: {exc}")
        traceback.print_exc()
    finally:
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
