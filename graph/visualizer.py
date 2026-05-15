import json
import matplotlib.pyplot as plt
import numpy as np
import os

def recreate_graph(data_path="graph/graph_data.json", time_range="7d"):
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Run scraper first.")
        return

    with open(data_path, "r") as f:
        all_data = json.load(f)

    if time_range not in all_data:
        print(f"Error: Time range {time_range} not found in data.")
        return

    data = all_data[time_range]
    points = data["points"]
    markers = data["markers"]
    metadata = data["metadata"]
    x_labels = data["x_labels"]
    legend = data.get("legend", {})

    def normalize_color(c):
        # Convert 'rgb(r, g, b)' to something comparable
        if c.startswith('rgb'):
            parts = [int(x.strip()) for x in c[4:-1].split(',')]
            return '#{:02x}{:02x}{:02x}'.format(*parts)
        return c.lower()

    # Create a mapping from color to label based on the legend
    color_to_label = {normalize_color(v): k.title() for k, v in legend.items()}
    # Fallbacks if legend is missing or incomplete
    if "#22c55e" not in color_to_label: color_to_label["#22c55e"] = "Peak"
    if "#f59e0b" not in color_to_label: color_to_label["#f59e0b"] = "Half-life"
    if "rgb(34, 197, 94)" not in color_to_label: color_to_label["rgb(34, 197, 94)"] = "Peak"
    if "rgb(245, 158, 11)" not in color_to_label: color_to_label["rgb(245, 158, 11)"] = "Half-life"

    # Baseline is at Y=35 in SVG coords. Peak is near Y=8.
    # In matplotlib, we want Y=0 to be the baseline.
    BASELINE_Y = 35
    
    xs = [p["x"] for p in points]
    ys = [BASELINE_Y - p["y"] for p in points]

    plt.figure(figsize=(12, 6), facecolor='white')
    
    # Fill area
    plt.fill_between(xs, ys, color='#3b82f6', alpha=0.1)
    # Main curve
    plt.plot(xs, ys, color='#3b82f6', linewidth=2.5, label='Concentration')

    # Markers
    for m in markers:
        mx = m["cx"]
        my = BASELINE_Y - m["cy"]
        m_color = normalize_color(m["fill"])
        label = color_to_label.get(m_color, "Marker")
        plt.scatter(mx, my, color=m["fill"], s=150, zorder=5, edgecolor='white', linewidth=1.5)
        
        # Add labels for markers
        plt.annotate(label, (mx, my), textcoords="offset points", xytext=(0,12), ha='center', 
                   fontweight='bold', color=m["fill"] if m["fill"] != "currentColor" else "black")

    # Axis lines (solid)
    plt.axhline(0, color='black', alpha=0.2, linewidth=1.5) # X-axis
    plt.axvline(xs[0], color='black', alpha=0.2, linewidth=1.5) # Y-axis
    
    # Y-axis dashed lines for labels (100%, 50%, etc.)
    y_labels = data.get("y_labels", [])
    for l in y_labels:
        plt.axhline(BASELINE_Y - l["pos"], color='black', linestyle='--', alpha=0.08, linewidth=0.8)

    # Format Axes
    plt.xticks([l["pos"] for l in x_labels], [l["text"] for l in x_labels])
    
    # Y-axis labels (the "left bar")
    y_labels = data.get("y_labels", [])
    if y_labels:
        # Sort by position to ensure labels are correct
        y_labels = sorted(y_labels, key=lambda x: x["pos"])
        y_pos = [BASELINE_Y - l["pos"] for l in y_labels]
        y_text = [l["text"] for l in y_labels]
        plt.yticks(y_pos, y_text, color='gray', alpha=0.6, fontsize=9)
    else:
        plt.yticks([])
    
    # Labels and Title
    plt.title(f"Pharmacokinetics ({time_range})\nPeak: {metadata['peak']} | Half-life: {metadata['half_life']}", pad=20)
    plt.xlabel("Time")
    plt.ylabel("Relative Concentration")
    
    # Clean up
    plt.grid(True, axis='x', alpha=0.05)
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['left'].set_visible(False)
    plt.gca().spines['bottom'].set_visible(False)
    
    output_path = f"graph/recreated_{time_range}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Recreated graph saved to {output_path}")

if __name__ == "__main__":
    import sys
    tr = sys.argv[1] if len(sys.argv) > 1 else "7d"
    
    if os.path.exists("graph/graph_data.json"):
        with open("graph/graph_data.json", "r") as f:
            all_keys = json.load(f).keys()
        for key in all_keys:
            recreate_graph(time_range=key)
    else:
        print("No data found. Please run scraper.py first.")
