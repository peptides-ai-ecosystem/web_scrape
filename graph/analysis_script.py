import sys
sys.stdout.reconfigure(encoding='utf-8')

# Check the x-label time values vs how our script interpolates

tabs = {
    '24h': {'total_h': 24, 'peak_cx': 14.3, 'peak_cy': 6.988, 'hl_cx': 28.06, 'hl_cy': 20.600,
            'labels': [('Dose',10,0), ('6h',31.5,6), ('12h',53,12), ('18h',74.5,18), ('1d',96,24)]},
    '7d':  {'total_h': 168, 'peak_cx': 10.86, 'peak_cy': 9.224, 'hl_cx': 12.58, 'hl_cy': 20.600,
            'labels': [('Dose',10,0), ('2d',31.5,48), ('4d',53,96), ('5d',74.5,120), ('7d',96,168)]},
    '14d': {'total_h': 336, 'peak_cx': 10.86, 'peak_cy': 15.734, 'hl_cx': 11.72, 'hl_cy': 24.237,
            'labels': [('Dose',10,0), ('4d',31.5,96), ('7d',53,168), ('11d',74.5,264), ('14d',96,336)]},
    '30d': {'total_h': 720, 'peak_cx': 10.86, 'peak_cy': 25.096, 'hl_cx': 10.86, 'hl_cy': 25.096,
            'labels': [('Dose',10,0), ('8d',31.5,192), ('15d',53,360), ('23d',74.5,552), ('30d',96,720)]},
}

def interp_labels(x, labels):
    """Our script's approach: interpolate between adjacent labels"""
    for i in range(len(labels)-1):
        _, x_a, t_a = labels[i]
        _, x_b, t_b = labels[i+1]
        if x >= x_a and x <= x_b:
            t = (x - x_a) / (x_b - x_a)
            return t_a + t * (t_b - t_a)
    return None

def direct_linear(x, total_h):
    """Direct linear mapping: time = ((x - 10) / 86) * total_hours"""
    return ((x - 10) / 86) * total_h

original = {
    '24h': {'peak_t': 1, 'peak_pct': 97, 'hl_t': 5, 'hl_pct': 50},
    '7d':  {'peak_t': 2, 'peak_pct': 89, 'hl_t': 5, 'hl_pct': 50},
    '14d': {'peak_t': 3, 'peak_pct': 66, 'hl_t': 7, 'hl_pct': 37},
    '30d': {'peak_t': 7, 'peak_pct': 34, 'hl_t': 7, 'hl_pct': 34},
}

ours_reported = {
    '24h': {'peak_t': 1.2, 'peak_pct': 97, 'hl_t': 5, 'hl_pct': 49},
    '7d':  {'peak_t': 1.9, 'peak_pct': 89, 'hl_t': 5.8, 'hl_pct': 49},
    '14d': {'peak_t': 3.8, 'peak_pct': 67, 'hl_t': 7.7, 'hl_pct': 37},
    '30d': {'peak_t': 7.7, 'peak_pct': 35, 'hl_t': 7.7, 'hl_pct': 35},
}

print("=== COMPARISON: OUR INTERPOLATION vs DIRECT LINEAR vs ORIGINAL ===")
print()

for tab in ['24h', '7d', '14d', '30d']:
    d = tabs[tab]
    orig = original[tab]
    ours = ours_reported[tab]
    
    # Our approach (label interpolation)
    peak_t_ours = interp_labels(d['peak_cx'], d['labels'])
    hl_t_ours = interp_labels(d['hl_cx'], d['labels'])
    
    # Direct linear
    peak_t_direct = direct_linear(d['peak_cx'], d['total_h'])
    hl_t_direct = direct_linear(d['hl_cx'], d['total_h'])
    
    # Y percentages
    peak_pct = ((35 - d['peak_cy']) / 29) * 100
    hl_pct = ((35 - d['hl_cy']) / 29) * 100
    
    print(f"--- {tab} ---")
    print(f"  Peak time:  ORIG={orig['peak_t']}h | INTERP={peak_t_ours:.2f}h | DIRECT={peak_t_direct:.2f}h | USER={ours['peak_t']}h")
    print(f"  HL time:    ORIG={orig['hl_t']}h | INTERP={hl_t_ours:.2f}h | DIRECT={hl_t_direct:.2f}h | USER={ours['hl_t']}h")
    print(f"  Peak %:     ORIG={orig['peak_pct']}% | CALC={peak_pct:.1f}%")
    print(f"  HL %:       ORIG={orig['hl_pct']}% | CALC={hl_pct:.1f}%")
    print()

print()
print("=== ROUNDING CHECK ===")
for tab in ['24h', '7d', '14d', '30d']:
    d = tabs[tab]
    peak_t = direct_linear(d['peak_cx'], d['total_h'])
    hl_t = direct_linear(d['hl_cx'], d['total_h'])
    peak_pct = ((35 - d['peak_cy']) / 29) * 100
    hl_pct = ((35 - d['hl_cy']) / 29) * 100
    print(f"{tab}: peak={peak_t:.2f}h->round={round(peak_t)}h(orig={original[tab]['peak_t']}h), hl={hl_t:.2f}h->round={round(hl_t)}h(orig={original[tab]['hl_t']}h)")
    print(f"      peak%={peak_pct:.1f}%->round={round(peak_pct)}%(orig={original[tab]['peak_pct']}%), hl%={hl_pct:.1f}%->round={round(hl_pct)}%(orig={original[tab]['hl_pct']}%)")
    print()

print()
print("=== KEY INSIGHT ===")
print()
print("The ORIGINAL website uses DIRECT LINEAR mapping (not label interpolation):")
print("  time = ((svgX - 10) / 86) * totalHours")
print()
print("AND it rounds time to nearest integer hour, and percentage to nearest integer.")
print()
print("Our script uses interpolateXLabel() which interpolates between adjacent x-axis")
print("labels. On the 24h tab, labels are evenly spaced in time, so it works OK.")
print("But on 7d/14d/30d tabs, the labels are NOT evenly spaced in time,")
print("causing incorrect time values!")
print()

# Let's verify the 7d label non-uniformity more clearly
print("=== 7d TAB X-LABELS ANALYSIS ===")
labels_7d = [('Dose',10,0), ('2d',31.5,48), ('4d',53,96), ('5d',74.5,120), ('7d',96,168)]
print("Label -> SVG X -> Time(h)")
for name, x, t in labels_7d:
    print(f"  {name:>4s} -> x={x:>5.1f} -> {t:>5.1f}h")
print()
print("Time gaps between labels:")
for i in range(len(labels_7d)-1):
    gap_h = labels_7d[i+1][2] - labels_7d[i][2]
    gap_x = labels_7d[i+1][1] - labels_7d[i][1]
    rate = gap_h / gap_x
    print(f"  {labels_7d[i][0]:>4s} -> {labels_7d[i+1][0]:>4s}: dx={gap_x:.1f} SVG units, dt={gap_h:.0f}h, rate={rate:.2f} h/SVG-unit")

print()
print("The rate h/SVG-unit varies! 2.23, 2.23, 1.12, 2.23")
print("Between 4d and 5d, the rate halves because 5d-4d=24h in 21.5 SVG units")
print("vs 2d-Dose=48h in 21.5 SVG units")
print()
print("But the actual SVG curve maps x LINEARLY to time: 1.95 h/SVG-unit everywhere")
print("The x-labels are just decorative markers, NOT defining the time mapping!")
