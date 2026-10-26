"""Task presets for the drop-down: what to tell the model, what to give it, a ready example.

The domains are the ones the ZTL stand has already judged against published worked examples (ztl-stand,
examples/real1..real4): the stand is known to handle each kind of problem, so a preset never promises more than
the stand can prove. `inputs` says which files help: photo (a nameplate, a label), pdf (a datasheet or a manual),
netlist+bom (a schematic tool's SPICE export and its bill of materials), deck (an ANSYS plane-truss deck).
"""

PRESETS = [
    {"id": "pump", "title": "Water pump — will it deliver?", "icon": "💧",
     "say": "Say what the pump must do (flow, lift height, pipe length and diameter) and ask whether this pump "
            "does it — or ask what head the pump needs.",
     "give": "A photo of the pump's nameplate or its datasheet PDF with the pump curve.",
     "example": "I need to lift 2 litres per second of water 20 m up through 60 m of 50 mm steel pipe. "
                "Will the pump on this nameplate do it? If not, what shut-off head would be enough?",
     "inputs": ["photo", "pdf"]},
    {"id": "dosing", "title": "Dosing pump — chlorine or chemical feed", "icon": "🧪",
     "say": "Give the water flow, the target dose and the chemical's strength; ask whether the pump's range covers it.",
     "give": "The dosing pump's datasheet or label (its min–max output).",
     "example": "A well delivers 30 m³/h and I need 2 mg/L of chlorine from 12.5% sodium hypochlorite. Can this "
                "dosing pump cover it across its range?",
     "inputs": ["photo", "pdf"]},
    {"id": "bearing", "title": "Bearing — will it last?", "icon": "⚙️",
     "say": "Give the load, the speed and the hours it must last; ask which bearing from a list passes.",
     "give": "A bearing catalogue page or datasheet (dynamic load rating Cr).",
     "example": "Radial load 6.5 kN at 1500 rpm, it must last 10 000 hours. Which of 6308 or 6309 is enough?",
     "inputs": ["photo", "pdf"]},
    {"id": "bolt", "title": "Bolted joint — preload with friction spread", "icon": "🔩",
     "say": "Give the bolt size and grade, the tightening torque and the friction range; ask for the guaranteed "
            "clamp force.",
     "give": "The bolt or fastener datasheet, or a handbook table.",
     "example": "M10 8.8 bolt tightened to 45 N·m, thread friction anywhere from 0.14 to 0.24. Is a clamp force "
                "of at least 20 kN guaranteed?",
     "inputs": ["photo", "pdf"]},
    {"id": "oring", "title": "O-ring groove — squeeze and fill", "icon": "⭕",
     "say": "Give the O-ring cross-section and the groove dimensions with tolerances; ask whether squeeze and "
            "fill stay in range.",
     "give": "The O-ring and groove drawing or the seal manufacturer's table.",
     "example": "O-ring 3.53 ±0.10 mm in a groove 2.8 ±0.05 deep and 4.8 wide. Does the squeeze stay between 15 "
                "and 30 % and the fill under 85 %?",
     "inputs": ["photo", "pdf"]},
    {"id": "heatsink", "title": "Heatsink — will the chip stay cool?", "icon": "🔥",
     "say": "Give the power dissipated, the ambient temperature and the limit; ask for the largest heatsink "
            "thermal resistance that still works.",
     "give": "The regulator or transistor datasheet (junction-to-case resistance, max junction temperature).",
     "example": "A linear regulator drops 12 V to 5 V at 1 A, ambient up to 40 °C. What is the largest heatsink "
                "resistance that keeps the junction under 125 °C?",
     "inputs": ["photo", "pdf"]},
    {"id": "regulator", "title": "Voltage regulator — divider tolerance", "icon": "🔌",
     "say": "Give the target output, the reference voltage and the resistor grades; ask whether the output stays "
            "within tolerance.",
     "give": "The regulator datasheet (reference voltage and its tolerance), or your schematic and BOM.",
     "example": "An adjustable regulator with Vref 1.25 V ±1% and 1% resistors must give 3.3 V within ±3%. "
                "Which standard E96 pair works?",
     "inputs": ["pdf", "netlist+bom"]},
    {"id": "circuit", "title": "Circuit from your CAD — SPICE + BOM", "icon": "🧩",
     "say": "Upload the SPICE netlist and the BOM, then say what must hold (a node voltage window, a power limit).",
     "give": "The netlist (.cir) your schematic tool exports and the BOM (.csv) with tolerances.",
     "example": "V(out) must stay between 4.7 and 5.4 V and no resistor may dissipate more than 0.25 W.",
     "inputs": ["netlist+bom"]},
    {"id": "adc", "title": "Amplifier + ADC error budget", "icon": "📈",
     "say": "Give the amplifier's offset and gain errors and the ADC's; ask whether the total stays within budget.",
     "give": "The amplifier and ADC datasheets.",
     "example": "Op-amp offset up to 1 mV, gain 10 with 0.1% resistors, 12-bit ADC with ±2 LSB. Is the total "
                "error under 0.5% of full scale?",
     "inputs": ["pdf"]},
    {"id": "ntc", "title": "Thermistor — trip temperatures", "icon": "🌡️",
     "say": "Give the NTC part, its divider and the comparator thresholds; ask the guaranteed trip temperatures.",
     "give": "The thermistor datasheet (R25, B value and tolerances).",
     "example": "10k NTC with B=3435 ±1% in a divider with a 10k 1% resistor from 3.3 V; the charger cuts off at "
                "73.5% of the supply. At what temperature does it trip, worst case?",
     "inputs": ["pdf"]},
    {"id": "fiber", "title": "Fiber link — power budget and reach", "icon": "🔦",
     "say": "Give transmitter power, receiver sensitivity, losses per km and per connector; ask the margin or "
            "the longest link.",
     "give": "The transceiver datasheet.",
     "example": "TX −3 to 0 dBm, RX sensitivity −20 dBm, 0.5 dB/km, 4 connectors at 0.5 dB, 3 dB safety margin. "
                "How long can the link be?",
     "inputs": ["pdf"]},
    {"id": "tube", "title": "Tube — allowed pressure", "icon": "🧯",
     "say": "Give the tube size, wall, material and temperature; ask the allowed working pressure.",
     "give": "The tubing catalogue page or material table.",
     "example": "1/2 inch 316 stainless tube, 0.049 inch wall, at 100 °F. What working pressure is allowed?",
     "inputs": ["photo", "pdf"]},
    {"id": "battery", "title": "Battery — how long will it last?", "icon": "🔋",
     "say": "Give the capacity, the average current and the derating factors; ask the guaranteed lifetime.",
     "give": "The battery datasheet and the board's current measurement or estimate.",
     "example": "CR2032, 225 mAh, average draw 3 µA at 25 °C, capacity derating 15–30%. Is 5 years guaranteed?",
     "inputs": ["photo", "pdf"]},
    {"id": "motor", "title": "Motor + gearhead — conveyor sizing", "icon": "🏭",
     "say": "Give the load, the belt speed and the gear ratio options; ask which motor and ratio work.",
     "give": "The motor and gearhead datasheets.",
     "example": "A conveyor moves 20 kg at 0.2 m/s on a 50 mm drive roller. Which of ratios 25, 50 or 100 with a "
                "1500 rpm motor gives the speed and enough torque?",
     "inputs": ["pdf"]},
    {"id": "truss", "title": "Truss — deflection from an ANSYS deck", "icon": "🌉",
     "say": "Upload the plane-truss deck and say the modulus tolerance and the deflection limit.",
     "give": "An ANSYS input deck (N, E, MP EX, R, D, F lines).",
     "example": "Modulus within ±0.5%. Node 42 must not sag more than 811 mm.",
     "inputs": ["deck"]},
]


def by_id(pid: str) -> dict:
    for p in PRESETS:
        if p["id"] == pid:
            return p
    return PRESETS[0]
