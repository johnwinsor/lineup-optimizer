from pybaseball import statcast
import pandas as pd

def test_pybaseball_spring():
    print("Testing pybaseball.statcast for a spring date (2026-03-10)...")
    try:
        # Requesting a single day to see if it returns spring training data
        data = statcast(start_dt='2026-03-10', end_dt='2026-03-10')
        if not data.empty:
            print(f"Success! Found {len(data)} rows.")
            print(f"Columns: {data.columns.tolist()[:10]}")
            # Check for non-empty launch_speed
            ev_data = data.dropna(subset=['launch_speed'])
            print(f"Rows with EV: {len(ev_data)}")
        else:
            print("No data returned for this date.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pybaseball_spring()
