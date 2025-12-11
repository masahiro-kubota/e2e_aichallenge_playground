import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.data import SimulationResult
from core.data.experiment import Artifact, ExperimentResult
from core.data.experiment.config import ResolvedExperimentConfig
from core.data.simulator import SimulationLog
from core.utils import get_project_root
from experiment.interfaces import ExperimentPostprocessor
from experiment.postprocessing.metrics import EvaluationMetrics, MetricsCalculator
from experiment.postprocessing.mlflow_logger import MLflowExperimentLogger


class EvaluationPostprocessor(ExperimentPostprocessor[SimulationResult, ExperimentResult]):
    """Postprocessor for evaluation experiments."""

    def __init__(self, config: ResolvedExperimentConfig) -> None:
        """Initialize evaluation postprocessor.

        Args:
            config: Experiment configuration
        """
        # 1. Initialize MLflow Logger
        self.mlflow_logger = MLflowExperimentLogger(
            tracking_uri=config.postprocess.mlflow.tracking_uri,
            experiment_name=config.experiment.name,
        )

        # 2. Initialize Metrics Calculator
        self.metrics_calculator = MetricsCalculator()

        # 3. Initialize Dashboard Generator (if enabled)
        self.dashboard_generator: Any | None = None
        self.dashboard_osm_path: Path | None = None
        self.dashboard_vehicle_params: dict[str, Any] | None = None

        if config.postprocess.dashboard.enabled:
            self._initialize_dashboard(config)

    def _initialize_dashboard(self, config: ResolvedExperimentConfig) -> None:
        """Initialize dashboard generator and resolve paths."""
        # Resolve Map Path
        map_path_str = config.postprocess.dashboard.map_path
        potential_path = Path(map_path_str)
        if not potential_path.is_absolute():
            potential_path = get_project_root() / potential_path

        if potential_path.exists():
            self.dashboard_osm_path = potential_path
        else:
            print(f"Warning: Configured dashboard map path not found: {potential_path}")

        # Resolve Vehicle Config
        self.dashboard_vehicle_params = self._load_vehicle_params(
            config.postprocess.dashboard.vehicle_config_path
        )

        # Initialize Generator
        try:
            import importlib

            dashboard_module = importlib.import_module("dashboard")
            generator_class = getattr(dashboard_module, "HTMLDashboardGenerator")
            self.dashboard_generator = generator_class()
        except (ImportError, AttributeError) as e:
            print(f"Warning: Could not load dashboard generator: {e}")

    def _load_vehicle_params(self, config_path_str: str) -> dict[str, Any] | None:
        """Load vehicle parameters from file."""
        import yaml

        vehicle_config_path = Path(config_path_str)
        if not vehicle_config_path.is_absolute():
            vehicle_config_path = get_project_root() / vehicle_config_path

        if vehicle_config_path.exists():
            try:
                with open(vehicle_config_path) as f:
                    vehicle_config = yaml.safe_load(f)

                return {
                    "width": vehicle_config.get("width"),
                    "wheelbase": vehicle_config.get("wheelbase"),
                    "front_overhang": vehicle_config.get("front_overhang"),
                    "rear_overhang": vehicle_config.get("rear_overhang"),
                }
            except Exception as e:
                print(f"Warning: Failed to load vehicle config from {vehicle_config_path}: {e}")
        else:
            print(f"Warning: Vehicle config path not found: {vehicle_config_path}")
        return None

    def _find_latest_mcap(self, output_dir: str | Path) -> Path | None:
        """Find the latest MCAP file in the output directory.

        Args:
            output_dir: Directory to search for MCAP files

        Returns:
            Path to the latest MCAP file, or None if not found
        """
        output_path = Path(output_dir)
        if not output_path.exists():
            return None

        # Find all MCAP files matching the pattern
        mcap_files = list(output_path.glob("simulation*.mcap"))
        if not mcap_files:
            return None

        # Return the most recently modified file
        return max(mcap_files, key=lambda p: p.stat().st_mtime)

    def process(
        self, result: SimulationResult, config: ResolvedExperimentConfig
    ) -> ExperimentResult:
        """Process evaluation results.

        Args:
            result: SimulationResult
            config: Experiment configuration

        Returns:
            Processed experiment result
        """
        # 1. Setup MLflow context
        mlflow_context = self._get_mlflow_context()

        # 2. Collect parameters
        result_params = self._collect_execution_params(config, result)

        # 3. Collect input artifacts
        result_artifacts = self._collect_input_artifacts(config)

        with mlflow_context:
            # 4. Save MCAP artifact if it exists (created by LoggerNode)
            mcap_path = None
            if config.postprocess.mcap.enabled:
                mcap_path = self._find_latest_mcap(config.postprocess.mcap.output_dir)
                if mcap_path:
                    result_artifacts.append(Artifact(local_path=mcap_path))

            # 5. Merge metadata into log
            self._update_log_metadata(result.log, result_params)

            # 6. Calculate metrics
            reason = getattr(result, "reason", "unknown")
            metrics_dict, metrics_obj = self._calculate_metrics(
                result.log, config, result.success, reason
            )

            # 7. Create ExperimentResult
            experiment_result = self._create_experiment_result(
                config, result, result_params, metrics_obj, result_artifacts
            )

            # 8. Generate Dashboard
            is_ci = bool(os.getenv("CI"))
            dashboard_artifact = self._generate_dashboard(experiment_result, config, is_ci)
            if dashboard_artifact:
                experiment_result.artifacts.append(dashboard_artifact)

            # 9. Log to MLflow
            self.mlflow_logger.log_result(experiment_result)

            # Clean up
            # Note: We keep the MCAP file as it is an output artifact.
            # Only unlink if you want to save space and rely on Artifact storage (if remote).
            # For now, let's keep it or unlink if verified uploaded.
            # Given the original code unlinked it, let's restore that behavior if we treat it as temp.
            # But the user wants proper logging. Let's assume Artifact handles it.
            if mcap_path.exists():
                # In original code it was unlinked.
                # If we want to persist it as a proper log, we might want to keep it or move it.
                # For now, consistent behavior: upload then delete local temp copy?
                # Actually, LoggerNode wrote it to a specific path.
                # If that path is temp, we delete it. If it's persistent, we keep it.
                pass  # Let's not delete it blindly since LoggerNode owns it now.

        return experiment_result

    def _get_mlflow_context(self) -> Any:
        """Get MLflow context manager."""
        if bool(os.getenv("CI")):
            from contextlib import nullcontext

            return nullcontext()
        return self.mlflow_logger.start_run()

    def _collect_execution_params(
        self, config: ResolvedExperimentConfig, result: SimulationResult
    ) -> dict[str, Any]:
        """Collect execution parameters from nodes and result."""
        ad_nodes_params = {}
        for node_config in config.nodes:
            if node_config.name not in ["Simulator", "Supervisor", "Logger"]:
                ad_nodes_params.update(node_config.params)

        return {
            **ad_nodes_params,
            "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "termination_reason": getattr(result, "reason", "unknown"),
        }

    def _update_log_metadata(self, log: SimulationLog, params: dict[str, Any]) -> None:
        """Update simulation log metadata with execution parameters."""
        existing_metadata = log.metadata.copy() if log.metadata else {}
        log.metadata = {**existing_metadata, **params}

        """Update simulation log metadata with execution parameters."""
        existing_metadata = log.metadata.copy() if log.metadata else {}
        log.metadata = {**existing_metadata, **params}

    def _create_experiment_result(
        self,
        config: ResolvedExperimentConfig,
        result: SimulationResult,
        params: dict[str, Any],
        metrics: EvaluationMetrics,
        artifacts: list[Artifact],
    ) -> ExperimentResult:
        """Create ExperimentResult object."""
        return ExperimentResult(
            experiment_name=config.experiment.name,
            experiment_type=config.experiment.type.value,
            execution_time=datetime.now(),
            simulation_results=[result],
            config=config,
            params=params,
            metrics=metrics,
            artifacts=artifacts,
        )

    def _collect_input_artifacts(self, config: ResolvedExperimentConfig) -> list[Artifact]:
        """Collect input artifacts from configuration."""
        artifacts: list[Artifact] = []
        for input_path in config.postprocess.inputs:
            full_path = get_project_root() / input_path
            if full_path.exists():
                artifacts.append(Artifact(local_path=full_path, remote_path="input_data"))
            else:
                print(f"Warning: Input file not found: {full_path}")
        return artifacts

    def _calculate_metrics(
        self,
        log: SimulationLog,
        config: ResolvedExperimentConfig,
        success: bool,
        reason: str = "unknown",
    ) -> tuple[dict[str, float], EvaluationMetrics]:
        """Calculate experiment metrics."""

        # If log is empty (streaming mode), try to recover last step from MCAP
        if not log.steps:
            mcap_path = None
            if config.postprocess.mcap.enabled:
                mcap_path = self._find_latest_mcap(config.postprocess.mcap.output_dir)
            if mcap_path and mcap_path.exists():
                try:
                    import json

                    from mcap.reader import make_reader

                    from core.data import Action, ADComponentLog, SimulationStep, VehicleState

                    last_step_dict = None
                    with open(mcap_path, "rb") as f:
                        reader = make_reader(f)
                        # Iterate all to get the last one (inefficient but simple for now)
                        # TODO: Seek to end if possible or generic optimization
                        for schema, channel, message in reader.iter_messages(
                            topics=["/simulation/step"]
                        ):
                            last_step_dict = json.loads(message.data)

                    if last_step_dict:
                        # Reconstruct simulation step from dict
                        # We only populate what MetricsCalculator needs (timestamp, info)
                        # MetricsCalculator uses: log.steps[-1].timestamp, log.steps[-1].info.get("goal_count")

                        step = SimulationStep(
                            timestamp=last_step_dict["timestamp"],
                            vehicle_state=VehicleState(
                                x=0.0,
                                y=0.0,
                                yaw=0.0,
                                velocity=0.0,
                                timestamp=last_step_dict["timestamp"],
                            ),  # Dummy
                            action=Action(steering=0.0, acceleration=0.0),  # Dummy
                            ad_component_log=ADComponentLog(
                                component_type="dummy", data={}
                            ),  # Dummy
                            info=last_step_dict.get("info", {}),
                        )
                        log.steps.append(step)

                except Exception as e:
                    print(f"Warning: Failed to recover metrics from MCAP: {e}")

        metrics = self.metrics_calculator.calculate(log, reason=reason)

        # Override success metric with SimulationResult.success
        metrics.success = 1.0 if success else 0.0

        # Convert metrics to flat dict for MLflow
        metrics_dict = {
            "lap_time": metrics.lap_time_sec,
            "collision_count": float(metrics.collision_count),
            "success": float(metrics.success),
            "termination_code": float(metrics.termination_code),
            "goal_count": float(metrics.goal_count),
        }

        return metrics_dict, metrics

    def _generate_dashboard(
        self, result: ExperimentResult, config: ResolvedExperimentConfig, is_ci: bool
    ) -> Artifact | None:
        """Generate interactive dashboard."""
        if not config.postprocess.dashboard.enabled or not self.dashboard_generator:
            return None

        print("Generating interactive dashboard...")
        import tempfile

        # Create a temporary file path
        # We close it immediately so the generator can open/write to it
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            dashboard_path = Path(f.name)

        try:
            self.dashboard_generator.generate(
                result, dashboard_path, self.dashboard_osm_path, self.dashboard_vehicle_params
            )
        except Exception as e:
            print(f"Warning: Dashboard generation failed: {e}")
            return None

        artifact = None
        if dashboard_path.exists():
            artifact = Artifact(local_path=dashboard_path)

            # Generate Screenshot
            try:
                target_path = get_project_root() / "dashboard_latest.png"
                screenshot_path = self._capture_dashboard_screenshot(dashboard_path, target_path)
                if screenshot_path and screenshot_path.exists():
                    print(f"Dashboard screenshot saved to {screenshot_path}")
                    # We can add it to artifacts or just keep it for the user to see
                    # Check if artifacts list supports multiple or if we append to experiment result
                    # The caller appends 'artifact' to experiment_result.artifacts
                    # We might want to return a list of artifacts or handle it here?
                    # The method signature returns `Artifact | None`.
                    # So we can't return multiple.
                    # We should probably manually append to result.artifacts here if we want both.
                    # Or change return type.
                    # For now, let's just print path and maybe copy it to a known location?
                    # Or better, let's allow returning a list? No, signature is fixed by interface?
                    # Interface says: -> Artifact | None
                    # So we can only return one artifact from here.
                    # But we can modify experiment_result.artifacts directly?
                    # Yes, result is passed by reference.
                    result.artifacts.append(Artifact(local_path=screenshot_path))
            except Exception as e:
                print(f"Warning: Dashboard screenshot failed: {e}")

        if is_ci:
            # In CI, save simulation log as JSON for dashboard injection
            ci_log_path = Path("simulation_log.json")
            result.simulation_results[0].log.save(ci_log_path)
            print(f"Simulation log saved to {ci_log_path} for CI dashboard injection")

            # Also save dashboard to persistent location for artifact upload
            ci_dashboard_path = Path("dashboard.html")
            if dashboard_path.exists():
                shutil.copy(dashboard_path, ci_dashboard_path)
                print(f"Dashboard saved to {ci_dashboard_path} for CI artifact upload")

        return artifact

    def _capture_dashboard_screenshot(
        self, html_path: Path, screenshot_path: Path | None = None
    ) -> Path | None:
        """Capture screenshot of the dashboard using Selenium."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            print("Warning: Selenium not installed. Skipping screenshot.")
            return None

        if screenshot_path is None:
            screenshot_path = get_project_root() / "dashboard_latest.png"
        else:
            screenshot_path = html_path.with_suffix(".png")

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # Suppress logging
        chrome_options.add_argument("--log-level=3")

        driver = None
        try:
            # Assuming chromedriver is in path or managed by selenium manager (newer selenium versions)
            driver = webdriver.Chrome(options=chrome_options)

            driver.get(f"file://{html_path.absolute()}")

            # Wait for dashboard to render (simple sleep for now, or check for element)
            import time

            time.sleep(2.0)  # Wait for React to mount and render map

            driver.save_screenshot(str(screenshot_path))

            return screenshot_path
        except Exception as e:
            print(f"Warning: Failed to capture screenshot: {e}")
            return None
        finally:
            if driver:
                driver.quit()
