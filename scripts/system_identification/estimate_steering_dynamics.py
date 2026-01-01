#!/usr/bin/env python3
# Usage:
#   uv run scripts/system_identification/estimate_steering_dynamics.py train scripts/system_identification/data/rosbag2_autoware_0.mcap
#   uv run scripts/system_identification/estimate_steering_dynamics.py eval scripts/system_identification/data/rosbag2_autoware_0.mcap --load-params scripts/system_identification/results/params.json
#   uv run scripts/system_identification/estimate_steering_dynamics.py --help
#
# Description:
#   MCAPからステアリング制御入力と車両ステータスを抽出し、FOPDT/SOPDTモデルのパラメータ推定を行います。

import argparse
import json
import sys
import yaml
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from core.utils.mcap_utils import read_messages
from scipy.interpolate import interp1d
from scipy.optimize import minimize


def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def extract_data(mcap_path):
    print(f"Extracting data from {mcap_path}...")
    cmd_times = []
    cmd_vals = []
    status_times = []
    status_vals = []
    vel_times = []
    vel_vals = []
    yaw_times = []
    yaw_vals = []

    cmd_topic = "/control/command/control_cmd"
    status_topic = "/vehicle/status/steering_status"
    state_topic = "/localization/kinematic_state"

    for topic, msg, timestamp_ns in read_messages(
        mcap_path, [cmd_topic, status_topic, state_topic]
    ):
        t = timestamp_ns / 1e9
        if topic == cmd_topic:
            try:
                val = msg.lateral.steering_tire_angle
                cmd_times.append(t)
                cmd_vals.append(val)
            except AttributeError:
                pass
        elif topic == status_topic:
            try:
                val = msg.steering_tire_angle
                status_times.append(t)
                status_vals.append(val)
            except AttributeError:
                pass
        elif topic == state_topic:
            try:
                v = msg.twist.twist.linear.x
                yaw_rate = msg.twist.twist.angular.z
                
                vel_times.append(t)
                vel_vals.append(v)
                yaw_times.append(t)
                yaw_vals.append(yaw_rate)
            except AttributeError:
                pass

    return (
        np.array(cmd_times),
        np.array(cmd_vals),
        np.array(status_times),
        np.array(status_vals),
        np.array(vel_times),
        np.array(vel_vals),
        np.array(yaw_times),
        np.array(yaw_vals),
    )


def simulate_yaw_fopdt(params, u_interp, t_span, u_times, v_interp, wheelbase):
    """
    Simulate FOPDT for Yaw Rate.
    YawRate(t) = (v(t) / L) * FOPDT_Steer(t)
    """
    # Use standard FOPDT simulation for the effective steering angle
    steer_eff = simulate_fopdt(params, u_interp, t_span, u_times)
    
    # Calculate Velocity factor
    v_vals = v_interp(t_span)
    
    # Yaw Rate = (v / L) * steer_eff
    y_sim = (v_vals / wheelbase) * steer_eff
    
    return y_sim, steer_eff


def cost_yaw_fopdt(params, u_interp, t_span, y_meas, u_times, v_interp, wheelbase):
    _, tau, delay_l = params
    if tau < 0 or delay_l < 0:
        return 1e9
        
    y_sim, _ = simulate_yaw_fopdt(params, u_interp, t_span, u_times, v_interp, wheelbase)
    return np.mean((y_sim - y_meas) ** 2)


def simulate_yaw_sopdt(params, u_interp, t_span, u_times, v_interp, wheelbase, max_rate=None):
    """
    Simulate SOPDT for Yaw Rate.
    YawRate(t) = (v(t) / L) * SOPDT_Steer(t)
    """
    # Use standard SOPDT simulation for the effective steering angle
    steer_eff = simulate_sopdt(params, u_interp, t_span, u_times, max_rate)
    
    # Calculate Velocity factor
    v_vals = v_interp(t_span)
    
    # Yaw Rate = (v / L) * steer_eff
    # We use small angle approximation tan(delta) ~ delta as per previous script
    y_sim = (v_vals / wheelbase) * steer_eff
    
    return y_sim, steer_eff


def cost_yaw_sopdt(params, u_interp, t_span, y_meas, u_times, v_interp, wheelbase):
    _, zeta, omega_n, delay_l = params
    if zeta < 0 or omega_n < 0 or delay_l < 0:
        return 1e9
        
    y_sim, _ = simulate_yaw_sopdt(params, u_interp, t_span, u_times, v_interp, wheelbase)
    return np.mean((y_sim - y_meas) ** 2)


def simulate_fopdt(params, u_interp, t_span, u_times):
    # params: [k_gain, tau, delay_l]
    k_gain, tau, delay_l = params
    dt = np.mean(np.diff(t_span))
    y_sim = np.zeros_like(t_span)

    # Initial condition
    y_sim[0] = u_interp(t_span[0] - delay_l) * k_gain  # Approximation

    alpha = np.exp(-dt / tau) if tau > 1e-4 else 0.0

    for i in range(1, len(t_span)):
        t_delayed = t_span[i] - delay_l
        u_val = u_interp(t_delayed) if t_delayed >= u_times[0] else u_interp(u_times[0])

        if tau > 1e-4:
            # Discrete LPF: y[k] = alpha*y[k-1] + (1-alpha)*K*u[k]
            y_sim[i] = alpha * y_sim[i - 1] + (1 - alpha) * k_gain * u_val
        else:
            y_sim[i] = k_gain * u_val

    return y_sim


def cost_fopdt(params, u_interp, t_span, y_meas, u_times):
    # Constraints can be handled by bounds in minimize, but here we penalize
    _, tau, delay_l = params
    if tau < 0 or delay_l < 0:
        return 1e9

    y_sim = simulate_fopdt(params, u_interp, t_span, u_times)
    return np.mean((y_sim - y_meas) ** 2)


def simulate_gain_delay(params, u_interp, t_span, u_times):
    # params: [k_gain, delay_l]
    k_gain, delay_l = params
    y_sim = np.zeros_like(t_span)
    for i, t in enumerate(t_span):
        t_delayed = t - delay_l
        u_val = u_interp(t_delayed) if t_delayed >= u_times[0] else u_interp(u_times[0])
        y_sim[i] = k_gain * u_val
    return y_sim


def cost_gain_delay(params, u_interp, t_span, y_meas, u_times):
    _, delay_l = params
    if delay_l < 0:
        return 1e9
    y_sim = simulate_gain_delay(params, u_interp, t_span, u_times)
    return np.mean((y_sim - y_meas) ** 2)


def simulate_sopdt(params, u_interp, t_span, u_times, max_rate=None):
    # params: [k_gain, zeta, omega_n, delay_l]
    k_gain, zeta, omega_n, delay_l = params
    dt = np.mean(np.diff(t_span))
    y_sim = np.zeros_like(t_span)

    # State variables: y (position), v (velocity)
    y = u_interp(t_span[0] - delay_l) * k_gain
    v = 0.0

    y_sim[0] = y

    # Pre-calc max delta if rate limited
    max_delta = max_rate * dt if max_rate is not None else float("inf")

    # Calculate discrete delay steps (Match simulator logic)
    delay_steps = max(1, int(delay_l / dt))

    for i in range(1, len(t_span)):
        # Discrete delay
        t_delayed_discrete = t_span[i] - (delay_steps * dt)
        u_val = (
            u_interp(t_delayed_discrete)
            if t_delayed_discrete >= u_times[0]
            else u_interp(u_times[0])
        )

        # Dynamics: y'' + 2*zeta*wn*y' + wn^2*y = K*wn^2*u
        # v' = K*wn^2*u - 2*zeta*wn*v - wn^2*y
        target = k_gain * u_val

        dv = (omega_n**2) * (target - y) - 2 * zeta * omega_n * v
        v_next = v + dv * dt

        # Rate Limiting (Match simulator/dynamics.py)
        delta = v_next * dt
        if abs(delta) > max_delta:
            delta = np.copysign(max_delta, delta)
            v_next = delta / dt

        y += delta
        v = v_next

        y_sim[i] = y

    return y_sim


def cost_sopdt(params, u_interp, t_span, y_meas, u_times):
    _, zeta, omega_n, delay_l = params
    if zeta < 0 or omega_n < 0 or delay_l < 0:
        return 1e9

    y_sim = simulate_sopdt(params, u_interp, t_span, u_times)
    return np.mean((y_sim - y_meas) ** 2)


def save_params(params_dict, filepath):
    with open(filepath, "w") as f:
        json.dump(params_dict, f, indent=4)
    print(f"Parameters saved to {filepath}")


def load_params(filepath):
    with open(filepath) as f:
        return json.load(f)


def run_optimization(u_interp, status_t, status_v, cmd_t, yaw_t=None, yaw_v=None, v_interp=None, wheelbase=None):
    # Optimize FOPDT (Steering)
    x0_fopdt = [1.0, 0.1, 0.05]
    bounds_fopdt = [(0.5, 2.0), (0.01, 2.0), (0.0, 1.0)]  # K, tau, L

    print("Optimizing FOPDT model (Steering)...")
    res_fopdt = minimize(
        cost_fopdt,
        x0_fopdt,
        args=(u_interp, status_t, status_v, cmd_t),
        bounds=bounds_fopdt,
        method="L-BFGS-B",
    )

    # Optimize SOPDT (Steering)
    x0_sopdt = [1.0, 0.7, 5.0, 0.05]
    bounds_sopdt = [(0.5, 2.0), (0.1, 2.0), (0.1, 20.0), (0.0, 1.0)]

    print("Optimizing SOPDT model (Steering)...")
    res_sopdt = minimize(
        cost_sopdt,
        x0_sopdt,
        args=(u_interp, status_t, status_v, cmd_t),
        bounds=bounds_sopdt,
        method="L-BFGS-B",
    )

    # Optimize Gain + Delay (Steering)
    x0_gd = [1.0, 0.05]
    bounds_gd = [(0.5, 2.0), (0.0, 1.0)]
    print("Optimizing Gain+Delay model (Steering)...")
    res_gd = minimize(
        cost_gain_delay,
        x0_gd,
        args=(u_interp, status_t, status_v, cmd_t),
        bounds=bounds_gd,
        method="L-BFGS-B",
    )

    # Optimize Yaw Rates
    res_yaw_sopdt = None
    res_yaw_fopdt = None
    if yaw_t is not None and yaw_v is not None and v_interp is not None and wheelbase is not None:
        # FOPDT (Yaw Rate)
        print("Optimizing FOPDT model (Yaw Rate)...")
        x0_yaw_fopdt = [0.8, res_fopdt.x[1], res_fopdt.x[2]]
        bounds_yaw_fopdt = [(0.4, 1.5), (0.01, 2.0), (0.0, 1.0)]
        res_yaw_fopdt = minimize(
            cost_yaw_fopdt,
            x0_yaw_fopdt,
            args=(u_interp, yaw_t, yaw_v, cmd_t, v_interp, wheelbase),
            bounds=bounds_yaw_fopdt,
            method="L-BFGS-B",
        )

        # SOPDT (Yaw Rate)
        print("Optimizing SOPDT model (Yaw Rate)...")
        # K, zeta, omega_n, L
        # Initial guess: K < 1.0 (slip), zeta ~ same, omega ~ same, delay ~ similar
        x0_yaw = [0.8, res_sopdt.x[1], res_sopdt.x[2], res_sopdt.x[3]] 
        bounds_yaw = [(0.4, 1.5), (0.1, 2.0), (0.1, 20.0), (0.0, 1.0)]
        
        res_yaw_sopdt = minimize(
            cost_yaw_sopdt,
            x0_yaw,
            args=(u_interp, yaw_t, yaw_v, cmd_t, v_interp, wheelbase),
            bounds=bounds_yaw,
            method="L-BFGS-B",
        )

    results = {
        "fopdt": {"K": res_fopdt.x[0], "tau": res_fopdt.x[1], "L": res_fopdt.x[2]},
        "sopdt": {
            "K": res_sopdt.x[0],
            "zeta": res_sopdt.x[1],
            "omega_n": res_sopdt.x[2],
            "L": res_sopdt.x[3],
        },
        "gain_delay": {"K": res_gd.x[0], "L": res_gd.x[1]},
    }
    
    if res_yaw_sopdt:
        results["yaw_sopdt"] = {
            "K": res_yaw_sopdt.x[0],
            "zeta": res_yaw_sopdt.x[1],
            "omega_n": res_yaw_sopdt.x[2],
            "L": res_yaw_sopdt.x[3],
        }
    if res_yaw_fopdt:
        results["yaw_fopdt"] = {
            "K": res_yaw_fopdt.x[0],
            "tau": res_yaw_fopdt.x[1],
            "L": res_yaw_fopdt.x[2],
        }

    return results


def evaluate_models(models_params, u_interp, status_t, status_v, cmd_t, yaw_t=None, yaw_v=None, v_interp=None, wheelbase=None):
    results = {}

    # FOPDT
    p_dict = models_params["fopdt"]
    p = [p_dict["K"], p_dict["tau"], p_dict["L"]]
    y_fopdt = simulate_fopdt(p, u_interp, status_t, cmd_t)
    rmse_fopdt = np.sqrt(np.mean((y_fopdt - status_v) ** 2))
    results["fopdt"] = {"y": y_fopdt, "rmse": rmse_fopdt, "params": p_dict}

    # SOPDT
    p_dict = models_params["sopdt"]
    p = [p_dict["K"], p_dict["zeta"], p_dict["omega_n"], p_dict["L"]]
    y_sopdt = simulate_sopdt(p, u_interp, status_t, cmd_t, max_rate=0.937)
    rmse_sopdt = np.sqrt(np.mean((y_sopdt - status_v) ** 2))
    results["sopdt"] = {"y": y_sopdt, "rmse": rmse_sopdt, "params": p_dict}

    # Gain + Delay
    if "gain_delay" in models_params:
        p_dict = models_params["gain_delay"]
        p = [p_dict["K"], p_dict["L"]]
        y_gd = simulate_gain_delay(p, u_interp, status_t, cmd_t)
        rmse_gd = np.sqrt(np.mean((y_gd - status_v) ** 2))
        results["gain_delay"] = {"y": y_gd, "rmse": rmse_gd, "params": p_dict}
        
    # Yaw Analysis
    if yaw_t is not None and yaw_v is not None:
        # Yaw SOPDT
        if "yaw_sopdt" in models_params:
            p_dict = models_params["yaw_sopdt"]
            p = [p_dict["K"], p_dict["zeta"], p_dict["omega_n"], p_dict["L"]]
            y_yaw, steer_eff = simulate_yaw_sopdt(p, u_interp, yaw_t, cmd_t, v_interp, wheelbase, max_rate=None)
            rmse_yaw = np.sqrt(np.mean((y_yaw - yaw_v) ** 2))
            results["yaw_sopdt"] = {"y": y_yaw, "rmse": rmse_yaw, "params": p_dict, "y_steer_eff": steer_eff}

        # Yaw FOPDT
        if "yaw_fopdt" in models_params:
            p_dict = models_params["yaw_fopdt"]
            p = [p_dict["K"], p_dict["tau"], p_dict["L"]]
            y_yaw, steer_eff = simulate_yaw_fopdt(p, u_interp, yaw_t, cmd_t, v_interp, wheelbase)
            rmse_yaw = np.sqrt(np.mean((y_yaw - yaw_v) ** 2))
            results["yaw_fopdt"] = {"y": y_yaw, "rmse": rmse_yaw, "params": p_dict, "y_steer_eff": steer_eff}

    return results


def print_results(results):
    print("\n" + "=" * 40)
    print("RESULTS: Steering Angle Dynamics")
    print("=" * 40)

    if "fopdt" in results:
        r = results["fopdt"]
        p = r["params"]
        print("Model: FOPDT (First Order)")
        print(f"  params: K={p['K']:.4f}, tau={p['tau']:.4f}, L={p['L']:.4f}")
        print(f"  RMSE: {r['rmse']:.6f}")
        print("-" * 20)

    if "sopdt" in results:
        r = results["sopdt"]
        p = r["params"]
        print("Model: SOPDT (Second Order)")
        print(
            f"  params: K={p['K']:.4f}, zeta={p['zeta']:.4f}, omega_n={p['omega_n']:.4f}, L={p['L']:.4f}"
        )
        print(f"  RMSE: {r['rmse']:.6f}")
        print("-" * 20)

    if "gain_delay" in results:
        r = results["gain_delay"]
        p = r["params"]
        print("Model: Gain + Delay")
        print(f"  params: K={p['K']:.4f}, L={p['L']:.4f}")
        print(f"  RMSE: {r['rmse']:.6f}")
        
    if "yaw_sopdt" in results or "yaw_fopdt" in results:
        print("\n" + "=" * 40)
        print("RESULTS: Yaw Rate Dynamics")
        print("=" * 40)
        
        if "yaw_fopdt" in results:
            r = results["yaw_fopdt"]
            p = r["params"]
            print("Model: FOPDT (SteerCmd -> YawRate)")
            print(f"  Equation: YawRate = (v/L) * FOPDT(SteerCmd)")
            print(f"  params: K_total={p['K']:.4f}, tau={p['tau']:.4f}, L={p['L']:.4f}")
            print(f"  RMSE: {r['rmse']:.6f}")
            print("-" * 20)

        if "yaw_sopdt" in results:
            r = results["yaw_sopdt"]
            p = r["params"]
            print("Model: SOPDT (SteerCmd -> YawRate)")
            print(f"  Equation: YawRate = (v/L) * SOPDT(SteerCmd)")
            print(
                f"  params: K_total={p['K']:.4f}, zeta={p['zeta']:.4f}, omega_n={p['omega_n']:.4f}, L={p['L']:.4f}"
            )
            print(f"  RMSE: {r['rmse']:.6f}")
            print(f"  (Note: K_total includes both actuator gain and tire slip factor)")


def plot_results(
    mcap_path, vel_t, vel_v, status_t, status_v, u_interp, results, yaw_t=None, yaw_v=None, mode_title="Identification"
):
    # Determine output directory (same dir as this script)
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    base_name = Path(mcap_path).stem

    y_fopdt = results["fopdt"]["y"]
    y_sopdt = results["sopdt"]["y"]
    rmse_fopdt = results["fopdt"]["rmse"]
    rmse_sopdt = results["sopdt"]["rmse"]
    
    y_yaw_sopdt = None
    if "yaw_sopdt" in results:
        y_yaw_sopdt = results["yaw_sopdt"]["y"]
        rmse_yaw_sopdt = results["yaw_sopdt"]["rmse"]
        
    y_yaw_fopdt = None
    if "yaw_fopdt" in results:
        y_yaw_fopdt = results["yaw_fopdt"]["y"]
        rmse_yaw_fopdt = results["yaw_fopdt"]["rmse"]

    # Matplotlib Plot
    rows = 5 if (y_yaw_sopdt is not None or y_yaw_fopdt is not None) else 3
    fig, axes = plt.subplots(
        rows, 1, figsize=(10, 3 * rows), sharex=True
    )
    if rows == 3:
        ax1, ax2, ax3 = axes
    else:
        ax1, ax2, ax3, ax4, ax5 = axes

    # Top: Velocity
    if len(vel_t) > 0:
        ax1.plot(vel_t, vel_v, "orange", label="Velocity")
        ax1.set_ylabel("Velocity (m/s)")
        ax1.legend()
        ax1.grid(True)

    # Middle 1: Steering
    ax2.plot(status_t, status_v, "k-", label="Measured", alpha=0.6)
    ax2.plot(status_t, u_interp(status_t), "k--", label="Command", alpha=0.3)
    ax2.plot(status_t, y_fopdt, "r-", label=f"FOPDT (RMSE={rmse_fopdt:.4f})")
    ax2.plot(status_t, y_sopdt, "g-", label=f"SOPDT (RMSE={rmse_sopdt:.4f})")
    ax2.legend()
    ax2.set_ylabel("Steer Angle (rad)")
    ax2.set_title(f"Steering Dynamics {mode_title}")
    ax2.grid(True)

    # Middle 2: Error
    ax3.plot(status_t, y_fopdt - status_v, "r-", label="Error (FOPDT)")
    ax3.plot(status_t, y_sopdt - status_v, "g-", label="Error (SOPDT)")
    ax3.set_ylabel("Steer Error (rad)")
    ax3.grid(True)
    ax3.legend()
    
    # Bottom 1: Yaw Rate (if available)
    if (y_yaw_sopdt is not None or y_yaw_fopdt is not None) and yaw_t is not None:
        ax4.plot(yaw_t, yaw_v, "k-", label="Measured YawRate", alpha=0.6)
        
        if y_yaw_fopdt is not None:
            ax4.plot(yaw_t, y_yaw_fopdt, "r-", label=f"FOPDT (RMSE={rmse_yaw_fopdt:.4f})")
            
        if y_yaw_sopdt is not None:
            ax4.plot(yaw_t, y_yaw_sopdt, "g-", label=f"SOPDT (RMSE={rmse_yaw_sopdt:.4f})")
        
        ax4.set_ylabel("Yaw Rate (rad/s)")
        ax4.set_title("Yaw Rate Dynamics")
        ax4.legend()
        ax4.grid(True)
        
        # Bottom 2: Yaw Rate Error
        if y_yaw_fopdt is not None:
            ax5.plot(yaw_t, y_yaw_fopdt - yaw_v, "r-", label="Error (FOPDT)")
        
        if y_yaw_sopdt is not None:
            ax5.plot(yaw_t, y_yaw_sopdt - yaw_v, "g-", label="Error (SOPDT)")
            
        ax5.set_ylabel("Yaw Rate Error (rad/s)")
        ax5.set_xlabel("Time (s)")
        ax5.legend()
        ax5.grid(True)
    else:
        ax3.set_xlabel("Time (s)")

    plt.tight_layout()

    output_png = output_dir / f"{base_name}.{mode_title.lower()}.png"
    plt.savefig(output_png)
    print(f"Plot saved to {output_png}")


def main():
    parser = argparse.ArgumentParser(description="Estimate or Evaluate steering and vehicle dynamics.")
    subparsers = parser.add_subparsers(dest="command", help="Mode: train or eval")

    # Train Parser
    parser_train = subparsers.add_parser("train", help="Estimate parameters from MCAP")
    parser_train.add_argument("file", help="Input MCAP file")
    parser_train.add_argument("config_file", help="Vehicle configuration file (yaml)")
    parser_train.add_argument(
        "--save-params", help="Path to save estimated parameters (JSON). Defaults to output dir."
    )

    # Eval Parser
    parser_eval = subparsers.add_parser("eval", help="Evaluate existing parameters on MCAP")
    parser_eval.add_argument("file", help="Input MCAP file")
    parser_eval.add_argument("config_file", help="Vehicle configuration file (yaml)")
    parser_eval.add_argument(
        "--load-params", required=True, help="Path to load parameters from (JSON)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    mcap_path = args.file
    config_path = args.config_file
    
    # Load vehicle config
    try:
        config = load_config(config_path)
        wheelbase = config["wheelbase"]
        print(f"Loaded config: wheelbase={wheelbase}")
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

    # 1. Extract Data
    cmd_t, cmd_v, status_t, status_v, vel_t, vel_v, yaw_t, yaw_v = extract_data(mcap_path)
    if len(cmd_t) == 0 or len(status_t) == 0:
        print("Error: No steering data found.")
        return

    # Normalize time
    t0 = min(cmd_t[0], status_t[0])
    if len(vel_t) > 0:
        t0 = min(t0, vel_t[0])
    
    cmd_t -= t0
    status_t -= t0
    if len(vel_t) > 0:
        vel_t -= t0
    if len(yaw_t) > 0:
        yaw_t -= t0

    # Sort
    idx = np.argsort(cmd_t)
    cmd_t = cmd_t[idx]
    cmd_v = cmd_v[idx]

    # Prepend a point before t=0 to represent the "initial state" avoid backward extrapolation of step input
    pre_t = cmd_t[0] - 1.0
    pre_v = status_v[0] if len(status_v) > 0 else 0.0

    cmd_t = np.insert(cmd_t, 0, pre_t)
    cmd_v = np.insert(cmd_v, 0, pre_v)

    u_interp = interp1d(
        cmd_t, cmd_v, kind="linear", fill_value=(pre_v, cmd_v[-1]), bounds_error=False
    )
    
    # Velocity interpolation for Yaw Model
    if len(vel_t) > 0:
        v_interp = interp1d(
            vel_t, vel_v, kind="linear", fill_value="extrapolate", bounds_error=False
        )
    else:
        v_interp = None
        print("Warning: No velocity data found. Yaw analysis will be skipped.")

    models_params = {}

    if args.command == "train":
        print("\n--- Training Mode ---")
        models_params = run_optimization(u_interp, status_t, status_v, cmd_t, yaw_t, yaw_v, v_interp, wheelbase)

        save_path = args.save_params
        if not save_path:
            output_dir = Path(__file__).parent / "results"
            output_dir.mkdir(exist_ok=True)
            save_path = output_dir / "params.json"

        save_params(models_params, save_path)

        results = evaluate_models(models_params, u_interp, status_t, status_v, cmd_t, yaw_t, yaw_v, v_interp, wheelbase)
        print_results(results)
        plot_results(
            mcap_path, vel_t, vel_v, status_t, status_v, u_interp, results, yaw_t, yaw_v, mode_title="Training"
        )

    elif args.command == "eval":
        print("\n--- Evaluation Mode ---")
        if not Path(args.load_params).exists():
            print(f"Error: Parameter file not found: {args.load_params}")
            sys.exit(1)

        models_params = load_params(args.load_params)
        print(f"Loaded parameters from {args.load_params}")

        results = evaluate_models(models_params, u_interp, status_t, status_v, cmd_t, yaw_t, yaw_v, v_interp, wheelbase)
        print_results(results)
        plot_results(
            mcap_path, vel_t, vel_v, status_t, status_v, u_interp, results, yaw_t, yaw_v, mode_title="Evaluation"
        )


if __name__ == "__main__":
    main()
