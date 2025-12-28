import hydra
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf
from pure_pursuit_controller.pure_pursuit_controller_node import PurePursuitControllerConfig

# Initialize Hydra
GlobalHydra.instance().clear()
hydra.initialize(config_path="../experiment/conf", version_base=None)

# Load config
cfg = hydra.compose(config_name="config", overrides=["agent=static_avoidance"])

# Extract controller params
# Note: In static_avoidance.yaml, the controller is under 'control' key, type is PurePursuitControllerNode
# We need to construct the config object manually from the dict to test validation
ctrl_params = cfg.agent.control.params

# Validate using Pydantic model
try:
    # Hydrate the object (OmegaConf to dict)
    params_dict = OmegaConf.to_container(ctrl_params, resolve=True)
    # Instantiate Pydantic model
    config_obj = PurePursuitControllerConfig(**params_dict)
    print("Configuration validation SUCCESS")
    print(config_obj)
except Exception as e:
    print("Configuration validation FAILED")
    print(e)
