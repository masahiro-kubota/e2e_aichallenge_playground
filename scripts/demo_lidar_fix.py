
import numpy as np

def demo():
    max_range = 30.0
    
    # 1. Simulator Output (JSON)
    # Simulator represents "no hit" (infinity) as null (None in Python)
    raw_sim_data = [5.5, 10.2, None, None, 2.1]
    
    print("--- 1. Raw Simulator Output (JSON/List) ---")
    print(f"Data: {raw_sim_data}")
    print("  -> 'None' means Infinite/No obstacle within range (SAFE)\n")

    # 2. Conversion to NumPy
    # np.array converts None to NaN for float arrays
    np_data = np.array(raw_sim_data, dtype=np.float32)
    
    print("--- 2. NumPy Conversion ---")
    print(f"Data: {np_data}")
    print("  -> 'None' became 'nan'\n")

    # 3. Current Implementation (The Bug)
    # extractor.py uses nan_to_num(nan=0.0) matches reference code
    # BUT reference code expects 'inf' for infinity, not 'nan'.
    current_processed = np.nan_to_num(np_data, nan=0.0, posinf=max_range, neginf=0.0)
    
    print("--- 3. Current Processing (BUG) ---")
    print(f"Code: np.nan_to_num(data, nan=0.0, posinf={max_range})")
    print(f"Result: {current_processed}")
    print("  -> 'nan' became 0.0")
    print("  -> Semantics: 0.0 usually means COLLISION or very close obstacle.")
    print("  -> AI learns: 'When safe (None), see 0.0 (Collision)' => CONFUSION\n")

    # 4. Proposed Fix
    # We allow 'nan' to be treated as max_range (Safe)
    proposed_processed = np.array(np_data) # copy
    # Explicitly replace nan with max_range
    proposed_processed = np.nan_to_num(proposed_processed, nan=max_range, posinf=max_range, neginf=0.0)

    print("--- 4. Proposed Fix ---")
    print(f"Code: np.nan_to_num(data, nan={max_range}, posinf={max_range})")
    print(f"Result: {proposed_processed}")
    print(f"  -> 'nan' became {max_range} (Max Range)")
    print("  -> Semantics: 30.0 means SAFE.")
    print("  -> AI learns: 'When safe (None), see 30.0' => CORRECT")

if __name__ == "__main__":
    demo()
